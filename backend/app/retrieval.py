"""Workspace-scoped lexical retrieval fallback for approved internal evidence.

This deliberately avoids claiming semantic/vector search. It ranks only explicitly
approved evidence in the current workspace and returns no source when there is no
meaningful overlap.
"""
import re
import math
from collections import Counter
from django.db import connection, DatabaseError

STOP_WORDS = {'the','and','for','that','with','from','this','your','have','are','was','were','into','our','their','they','them','then','than','will','would','could','should','about','over','under','more','most','less','very','also','not','but','you','all','has','had','can','may','might','its','a','an','of','to','in','on','at','by','as','is','be','or','if','we','it'}

def _terms(value):
    return [t for t in re.findall(r"[a-z0-9]{3,}", (value or '').lower()) if t not in STOP_WORDS]

def retrieve_evidence(workspace, query, limit=8):
    query_terms=Counter(_terms(query))
    if not query_terms:
        return []
    ranked=[]
    for source in workspace.evidence_sources.filter(approved=True).order_by('-created_at'):
        source_terms=Counter(_terms(f'{source.name} {source.passage} {source.location}'))
        overlap=query_terms.keys() & source_terms.keys()
        if not overlap:
            continue
        # IDF-free lexical score is transparent and used only to select context.
        score=sum(min(query_terms[t], source_terms[t]) for t in overlap) / (sum(query_terms.values()) ** 0.5)
        ranked.append((score, source))
    ranked.sort(key=lambda item:(item[0], item[1].created_at), reverse=True)
    return [source for score, source in ranked[:limit] if score > 0]

def _pgvector_rows(workspace_id, query_vector, model, item_type, limit):
    """Return HNSW-ranked object IDs, or None when pgvector cannot serve this query."""
    if connection.vendor!='postgresql' or len(query_vector)!=1536:
        return None
    if item_type=='evidence':
        joins='JOIN app_evidencesource es ON es.id = ei.evidence_source_id'
        item_column='es.id'
        eligibility='AND es.approved = TRUE AND es.workspace_id = ei.workspace_id'
    else:
        joins='JOIN app_guidelinechunk gc ON gc.id = ei.guideline_chunk_id JOIN app_guideline g ON g.id = gc.guideline_id'
        item_column='gc.id'
        eligibility='AND g.workspace_id = ei.workspace_id AND gc.version = g.version'
    literal='['+','.join(format(float(value),'.9g') for value in query_vector)+']'
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT {item_column}, 1 - (ei.embedding_vector <=> %s::vector) AS similarity '
                f'FROM app_embeddingindex ei {joins} WHERE ei.workspace_id = %s AND ei.embedding_model = %s '
                f'AND ei.embedding_vector IS NOT NULL {eligibility} '
                f'ORDER BY ei.embedding_vector <=> %s::vector LIMIT %s',
                [literal,workspace_id,model,literal,limit],
            )
            rows=[(int(object_id),float(score)) for object_id,score in cursor.fetchall()]
        return rows or None
    except DatabaseError:
        # This keeps SQLite and databases not yet migrated on the JSON cosine path.
        return None

def _pgvector_column_available():
    """Do not assume the optional vector extension migration succeeded."""
    if connection.vendor != 'postgresql':
        return False
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'app_embeddingindex' "
                "AND column_name = 'embedding_vector')"
            )
            return bool(cursor.fetchone()[0])
    except DatabaseError:
        return False

def sync_embedding_index(*,workspace,embedding,model,evidence_source=None,guideline_chunk=None):
    """Mirror JSON embeddings into the retrieval index and pgvector when supported."""
    if not embedding or (evidence_source is None)==(guideline_chunk is None):
        return
    from .models import EmbeddingIndex
    lookup={'evidence_source':evidence_source,'embedding_model':model} if evidence_source else {'guideline_chunk':guideline_chunk,'embedding_model':model}
    values=[float(value) for value in embedding]
    row,created=EmbeddingIndex.objects.get_or_create(**lookup,defaults={'workspace':workspace,'dimensions':len(values),'embedding_json':values})
    if not created and (row.embedding_json!=values or row.dimensions!=len(values) or row.workspace_id!=workspace.id):
        row.workspace=workspace;row.dimensions=len(values);row.embedding_json=values
        row.save(update_fields=['workspace','dimensions','embedding_json','updated_at'])
    if connection.vendor=='postgresql' and len(values)==1536 and _pgvector_column_available():
        literal='['+','.join(format(value,'.9g') for value in values)+']'
        with connection.cursor() as cursor:
            cursor.execute('UPDATE app_embeddingindex SET embedding_vector = %s::vector WHERE id = %s',[literal,row.id])

def _objects_in_rank_order(model_class, rows, limit=8):
    ids=[object_id for object_id,score in rows if score>=0.2]
    if not ids:return []
    objects={obj.id:obj for obj in model_class.objects.filter(id__in=ids)}
    return [objects[object_id] for object_id in ids if object_id in objects][:limit]

def _rank_fusion(vector_rows, lexical_rows, limit=8):
    """Reciprocal-rank fusion: combine semantic and transparent lexical matches."""
    scores={};objects={}
    for rows in (vector_rows,lexical_rows):
        for rank,obj in enumerate(rows,1):
            objects[obj.id]=obj
            scores[obj.id]=scores.get(obj.id,0.0)+1.0/(60+rank)
    return [objects[object_id] for object_id,_ in sorted(scores.items(),key=lambda item:(-item[1],item[0]))[:limit]]

def _cosine_ranked(query_vector, objects, model, limit):
    norm=math.sqrt(sum(value*value for value in query_vector))
    ranked=[]
    if not norm:return []
    for obj in objects:
        vector=obj.embedding if hasattr(obj,'embedding') else []
        vector_model=obj.embedding_model if hasattr(obj,'embedding_model') else ''
        if not isinstance(vector,list) or len(vector)!=len(query_vector) or vector_model!=model:continue
        obj_norm=math.sqrt(sum(value*value for value in vector))
        if not obj_norm:continue
        score=sum(a*b for a,b in zip(query_vector,vector))/(norm*obj_norm)
        if score>=0.2:ranked.append((score,obj))
    ranked.sort(key=lambda item:(-item[0],item[1].id))
    return [obj for _,obj in ranked[:limit]]

def retrieve_evidence_with_embeddings(workspace, query, query_vector, model, limit=8):
    """Fuse semantic and lexical results while restricting semantic sources to approved rows."""
    if not query_vector:
        return [], 'embeddings_unavailable'
    if not any(query_vector):return [],'embeddings_unavailable'
    pg_rows=_pgvector_rows(workspace.id,query_vector,model,'evidence',limit)
    if pg_rows is not None:
        from .models import EvidenceSource
        vector_rows=[source for source in _objects_in_rank_order(EvidenceSource,pg_rows,limit) if source.workspace_id==workspace.id and source.approved];method='pgvector_hybrid'
    else:
        sources=workspace.evidence_sources.filter(approved=True,embedding_model=model).exclude(embedding=[])
        vector_rows=_cosine_ranked(query_vector,sources,model,limit);method='embeddings_hybrid'
    if not vector_rows:return [],'embeddings_empty'
    lexical_rows=retrieve_evidence(workspace,query,limit)
    return _rank_fusion(vector_rows,lexical_rows,limit),method

def retrieve_guideline_chunks(workspace, query, query_vector=None, model=None, limit=8):
    from django.db.models import F
    from .models import GuidelineChunk
    chunks=GuidelineChunk.objects.filter(guideline__workspace=workspace,version=F('guideline__version')).select_related('guideline')
    lexical_rows=[]
    query_terms=Counter(_terms(query))
    if query_terms:
        lexical_ranked=[]
        for chunk in chunks:
            terms=Counter(_terms(chunk.text));overlap=query_terms.keys() & terms.keys()
            if overlap:lexical_ranked.append((sum(min(query_terms[t],terms[t]) for t in overlap)/(sum(query_terms.values())**0.5),chunk))
        lexical_ranked.sort(key=lambda item:(-item[0],item[1].id))
        lexical_rows=[chunk for score,chunk in lexical_ranked[:limit] if score>0]
    if query_vector and any(query_vector):
        pg_rows=_pgvector_rows(workspace.id,query_vector,model,'guideline',limit)
        if pg_rows is not None:
            vector_rows=[chunk for chunk in _objects_in_rank_order(GuidelineChunk,pg_rows,limit) if chunk.guideline.workspace_id==workspace.id and chunk.version==chunk.guideline.version];method='pgvector_hybrid'
        else:
            vector_rows=_cosine_ranked(query_vector,[chunk for chunk in chunks if not model or chunk.embedding_model==model],model,limit);method='embeddings_hybrid'
        if vector_rows:return _rank_fusion(vector_rows,lexical_rows,limit),method
    return lexical_rows,'lexical'
