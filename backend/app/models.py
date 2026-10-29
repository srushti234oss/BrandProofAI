import uuid
from django.db import models
from django.contrib.auth.models import User
class Workspace(models.Model):
    name=models.CharField(max_length=160)
    retention_days=models.PositiveIntegerField(null=True,blank=True,default=None)
    created_at=models.DateTimeField(auto_now_add=True)
class Membership(models.Model):
    ROLE=[('admin','Admin'),('manager','Brand manager'),('reviewer','Reviewer'),('creator','Creator')]
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='members')
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    role=models.CharField(max_length=20,choices=ROLE,default='admin')
    class Meta: unique_together=[('workspace','user')]

class WorkspaceInvitation(models.Model):
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='invitations')
    email=models.EmailField()
    role=models.CharField(max_length=20,choices=Membership.ROLE,default='creator')
    token_hash=models.CharField(max_length=64,unique=True)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='sent_workspace_invitations')
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    accepted_at=models.DateTimeField(null=True,blank=True)
    accepted_by=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='accepted_workspace_invitations')
class Guideline(models.Model):
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='guidelines')
    name=models.CharField(max_length=200)
    version=models.PositiveIntegerField(default=1)
    source_text=models.TextField(blank=True)
    source_file=models.FileField(upload_to='guidelines/',blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
class Rule(models.Model):
    CATEGORIES=[('prohibited','Prohibited term'),('preferred','Preferred term'),('tone','Tone'),('claim','Claim'),('general','General')]
    guideline=models.ForeignKey(Guideline,on_delete=models.CASCADE,related_name='rules')
    title=models.CharField(max_length=200)
    text=models.TextField()
    category=models.CharField(max_length=20,choices=CATEGORIES,default='general')
    severity=models.CharField(max_length=20,default='medium')
    replacement=models.CharField(max_length=200,blank=True)
    active=models.BooleanField(default=True)
class Asset(models.Model):
    STATUS=[('queued','Queued'),('processing','Processing'),('completed','Completed'),('warnings','Completed with warnings'),('failed','Failed')]
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='assets')
    title=models.CharField(max_length=240)
    campaign=models.CharField(max_length=240,blank=True)
    description=models.TextField(blank=True)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    status=models.CharField(max_length=20,choices=STATUS,default='queued')
    latest_version=models.PositiveIntegerField(default=1)
    source_file=models.FileField(upload_to='submitted/',blank=True)
class AssetVersion(models.Model):
    asset=models.ForeignKey(Asset,on_delete=models.CASCADE,related_name='versions')
    number=models.PositiveIntegerField()
    content=models.TextField(blank=True)
    extracted_text=models.TextField(blank=True)
    extraction_method=models.CharField(max_length=40,default='pasted_text')
    extraction_status=models.CharField(max_length=20,default='completed')
    extraction_warnings=models.JSONField(default=list,blank=True)
    extraction_metadata=models.JSONField(default=dict,blank=True)
    content_hash=models.CharField(max_length=64)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: unique_together=[('asset','number')]
class Finding(models.Model):
    STATES=[('open','Open'),('discussion','In discussion'),('changes_requested','Changes requested'),('resolved','Resolved'),('dismissed','Dismissed')]
    version=models.ForeignKey(AssetVersion,on_delete=models.CASCADE,related_name='findings')
    kind=models.CharField(max_length=40)
    severity=models.CharField(max_length=20,default='medium')
    text=models.TextField()
    explanation=models.TextField()
    status=models.CharField(max_length=30,choices=STATES,default='open')
    rule=models.ForeignKey(Rule,null=True,blank=True,on_delete=models.SET_NULL)
    claim=models.ForeignKey('ExtractedClaim',null=True,blank=True,on_delete=models.SET_NULL,related_name='findings')
    assigned_to=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='assigned_brand_findings')
    location=models.JSONField(default=dict,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
class Comment(models.Model):
    finding=models.ForeignKey(Finding,on_delete=models.CASCADE,related_name='comments')
    author=models.ForeignKey(User,on_delete=models.PROTECT)
    body=models.TextField()
    parent=models.ForeignKey('self',null=True,blank=True,on_delete=models.CASCADE,related_name='replies')
    created_at=models.DateTimeField(auto_now_add=True)
class Review(models.Model):
    STATES=[('submitted','Submitted'),('changes_requested','Changes requested'),('approved','Approved'),('rejected','Rejected')]
    version=models.ForeignKey(AssetVersion,on_delete=models.CASCADE,related_name='reviews')
    state=models.CharField(max_length=30,choices=STATES)
    reviewer=models.ForeignKey(User,on_delete=models.PROTECT)
    reason=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
class AuditEvent(models.Model):
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE)
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    action=models.CharField(max_length=80)
    details=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)

class GuidelineVersion(models.Model):
    guideline=models.ForeignKey(Guideline,on_delete=models.CASCADE,related_name='versions')
    number=models.PositiveIntegerField()
    snapshot=models.JSONField(default=dict)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: unique_together=[('guideline','number')]

class GuidelineChunk(models.Model):
    guideline=models.ForeignKey(Guideline,on_delete=models.CASCADE,related_name='chunks')
    version=models.PositiveIntegerField()
    index=models.PositiveIntegerField()
    text=models.TextField()
    location=models.CharField(max_length=240,blank=True)
    embedding=models.JSONField(default=list,blank=True)
    embedding_model=models.CharField(max_length=160,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together=[('guideline','version','index')]
        indexes=[models.Index(fields=['guideline','version'])]

class EmbeddingIndex(models.Model):
    """Retrieval metadata; PostgreSQL adds an indexed pgvector column by migration."""
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='embedding_indexes')
    evidence_source=models.ForeignKey('EvidenceSource',null=True,blank=True,on_delete=models.CASCADE,related_name='embedding_indexes')
    guideline_chunk=models.ForeignKey(GuidelineChunk,null=True,blank=True,on_delete=models.CASCADE,related_name='embedding_indexes')
    embedding_model=models.CharField(max_length=160)
    dimensions=models.PositiveIntegerField()
    embedding_json=models.JSONField(default=list)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[
            models.CheckConstraint(check=(models.Q(evidence_source__isnull=False,guideline_chunk__isnull=True)|models.Q(evidence_source__isnull=True,guideline_chunk__isnull=False)),name='embedding_index_one_source'),
            models.UniqueConstraint(fields=['evidence_source','embedding_model'],name='unique_evidence_embedding_model'),
            models.UniqueConstraint(fields=['guideline_chunk','embedding_model'],name='unique_guideline_embedding_model'),
        ]

class ApprovedExample(models.Model):
    guideline=models.ForeignKey(Guideline,on_delete=models.CASCADE,related_name='examples')
    text=models.TextField()
    approved=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)

class EvidenceSource(models.Model):
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='evidence_sources')
    name=models.CharField(max_length=240)
    source_type=models.CharField(max_length=40,default='internal')
    passage=models.TextField(blank=True)
    location=models.CharField(max_length=240,blank=True)
    source_file=models.FileField(upload_to='evidence/',blank=True)
    extraction_warnings=models.JSONField(default=list,blank=True)
    approved=models.BooleanField(default=False)
    embedding=models.JSONField(default=list,blank=True)
    embedding_model=models.CharField(max_length=160,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class ExtractedClaim(models.Model):
    CLASSES=[('supported','Supported'),('contradicted','Contradicted'),('unverified','Unverified'),('uncertain','Uncertain')]
    version=models.ForeignKey(AssetVersion,on_delete=models.CASCADE,related_name='claims')
    wording=models.TextField()
    location=models.CharField(max_length=120,blank=True)
    category=models.CharField(max_length=40,default='promotional')
    classification=models.CharField(max_length=20,choices=CLASSES,default='unverified')
    explanation=models.TextField()
    created_at=models.DateTimeField(auto_now_add=True)

class EvidenceReference(models.Model):
    claim=models.ForeignKey(ExtractedClaim,null=True,blank=True,on_delete=models.CASCADE,related_name='references')
    finding=models.ForeignKey(Finding,null=True,blank=True,on_delete=models.CASCADE,related_name='evidence_references')
    source=models.ForeignKey(EvidenceSource,on_delete=models.PROTECT)
    passage=models.TextField(blank=True)
    location=models.CharField(max_length=240,blank=True)

class GuidelineReference(models.Model):
    claim=models.ForeignKey(ExtractedClaim,on_delete=models.CASCADE,related_name='guideline_references')
    chunk=models.ForeignKey(GuidelineChunk,on_delete=models.PROTECT,related_name='claim_references')
    passage=models.TextField(blank=True)
    location=models.CharField(max_length=240,blank=True)

class CorrectionSuggestion(models.Model):
    SCOPES=[('full_content','Full content'),('fragment','Text fragment')]
    finding=models.ForeignKey(Finding,on_delete=models.CASCADE,related_name='suggestions')
    minimal_edit=models.TextField()
    clearer_rewrite=models.TextField()
    rationale=models.TextField()
    method=models.CharField(max_length=60,default='rule-based draft')
    scope=models.CharField(max_length=20,choices=SCOPES,default='fragment')
    created_at=models.DateTimeField(auto_now_add=True)

class BrandPaletteEntry(models.Model):
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='palette')
    name=models.CharField(max_length=100)
    hex_value=models.CharField(max_length=7)

class ReferenceLogo(models.Model):
    workspace=models.ForeignKey(Workspace,on_delete=models.CASCADE,related_name='logos')
    name=models.CharField(max_length=160)
    image=models.ImageField(upload_to='reference-logos/')
    created_at=models.DateTimeField(auto_now_add=True)

class AnalysisRun(models.Model):
    STATES=[('queued','Queued'),('processing','Processing'),('completed','Completed'),('warnings','Completed with warnings'),('failed','Failed')]
    version=models.ForeignKey(AssetVersion,on_delete=models.CASCADE,related_name='analysis_runs')
    state=models.CharField(max_length=20,choices=STATES,default='queued')
    warnings=models.JSONField(default=list)
    errors=models.JSONField(default=list)
    attempts=models.PositiveIntegerField(default=0)
    started_at=models.DateTimeField(null=True,blank=True)
    finished_at=models.DateTimeField(null=True,blank=True)

class GuidelineClarityInsight(models.Model):
    guideline=models.ForeignKey(Guideline,on_delete=models.CASCADE,related_name='insights')
    rule=models.ForeignKey(Rule,on_delete=models.CASCADE,related_name='insights')
    signal_count=models.PositiveIntegerField(default=0)
    signal_summary=models.JSONField(default=list)
    proposed_text=models.TextField(blank=True)
    state=models.CharField(max_length=20,default='candidate')
    created_at=models.DateTimeField(auto_now_add=True)

class FindingStatusEvent(models.Model):
    finding=models.ForeignKey(Finding,on_delete=models.CASCADE,related_name='status_events')
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    previous=models.CharField(max_length=30)
    current=models.CharField(max_length=30)
    reason=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
