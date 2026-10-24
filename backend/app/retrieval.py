"""Workspace-scoped lexical retrieval fallback for approved internal evidence.

This deliberately avoids claiming semantic/vector search. It ranks only explicitly
approved evidence in the current workspace and returns no source when there is no
meaningful overlap.
"""
import re
import math
from collections import Counter

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

def retrieve_evidence_with_embeddings(workspace, query, query_vector, model, limit=8):
    """Rank same-workspace approved sources by cosine similarity when vectors exist."""
    if not query_vector:
        return [], 'embeddings_unavailable'
    norm=math.sqrt(sum(value*value for value in query_vector))
    if not norm:
        return [], 'embeddings_unavailable'
    ranked=[]
    for source in workspace.evidence_sources.filter(approved=True,embedding_model=model).exclude(embedding=[]):
        vector=source.embedding
        if not isinstance(vector,list) or len(vector)!=len(query_vector):
            continue
        source_norm=math.sqrt(sum(value*value for value in vector))
        if not source_norm:
            continue
        score=sum(a*b for a,b in zip(query_vector,vector))/(norm*source_norm)
        ranked.append((score,source))
    if not ranked:
        return [], 'embeddings_empty'
    ranked.sort(key=lambda item:(item[0],item[1].created_at),reverse=True)
    return [source for score,source in ranked[:limit] if score>=0.2], 'embeddings_cosine'

def retrieve_guideline_chunks(workspace, query, query_vector=None, model=None, limit=8):
    from django.db.models import F
    from .models import GuidelineChunk
    chunks=GuidelineChunk.objects.filter(guideline__workspace=workspace,version=F('guideline__version')).select_related('guideline')
    if query_vector:
        norm=math.sqrt(sum(value*value for value in query_vector));ranked=[]
        if norm:
            for chunk in chunks:
                if model and chunk.embedding_model!=model:continue
                vector=chunk.embedding
                if not vector or len(vector)!=len(query_vector):continue
                chunk_norm=math.sqrt(sum(value*value for value in vector))
                if chunk_norm:ranked.append((sum(a*b for a,b in zip(query_vector,vector))/(norm*chunk_norm),chunk))
        if ranked:
            ranked.sort(key=lambda item:(item[0],item[1].id),reverse=True)
            return [chunk for score,chunk in ranked[:limit] if score>=0.2],'embeddings_cosine'
    query_terms=Counter(_terms(query));ranked=[]
    if not query_terms:return [],'lexical'
    for chunk in chunks:
        terms=Counter(_terms(chunk.text));overlap=query_terms.keys() & terms.keys()
        if overlap:ranked.append((sum(min(query_terms[t],terms[t]) for t in overlap)/(sum(query_terms.values())**0.5),chunk))
    ranked.sort(key=lambda item:(item[0],item[1].id),reverse=True)
    return [chunk for score,chunk in ranked[:limit] if score>0],'lexical'
