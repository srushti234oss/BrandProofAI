from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from app.models import Workspace, Membership, Asset, AuditEvent

class Command(BaseCommand):
    help='Delete assets older than each workspace retention_days policy; run on a trusted schedule.'
    def add_arguments(self,parser):parser.add_argument('--dry-run',action='store_true')
    def handle(self,*args,**opts):
        cutoff_now=timezone.now();deleted=0
        for workspace in Workspace.objects.exclude(retention_days__isnull=True):
            cutoff=cutoff_now-timedelta(days=workspace.retention_days)
            expired=list(Asset.objects.filter(workspace=workspace,created_at__lt=cutoff).order_by('id'))
            if not expired:continue
            admin=Membership.objects.filter(workspace=workspace,role='admin').select_related('user').first()
            if not admin:
                self.stderr.write(f'Skipped workspace {workspace.id}: no admin actor exists for audited retention deletion.')
                continue
            if opts['dry_run']:
                self.stdout.write(f'Would delete {len(expired)} assets from workspace {workspace.id}.');deleted+=len(expired);continue
            files=[(a.source_file.storage,a.source_file.name) for a in expired if a.source_file]
            ids=[a.id for a in expired]
            with transaction.atomic():
                Asset.objects.filter(id__in=ids,workspace=workspace).delete()
                AuditEvent.objects.create(workspace=workspace,actor=admin.user,action='retention_assets_purged',details={'asset_ids':ids,'cutoff':cutoff.isoformat(),'count':len(ids)})
                for storage,name in files:transaction.on_commit(lambda storage=storage,name=name:storage.delete(name))
            deleted+=len(ids)
            self.stdout.write(f'Deleted {len(ids)} expired assets from workspace {workspace.id}.')
        self.stdout.write(f'{"Would delete" if opts["dry_run"] else "Deleted"} {deleted} assets total.')
