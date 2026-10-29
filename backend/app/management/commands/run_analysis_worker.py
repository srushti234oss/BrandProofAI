import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from app.models import AnalysisRun
from app.views import process_analysis_run

class Command(BaseCommand):
    help='Run durable BrandProof analysis jobs from the database queue.'
    def add_arguments(self,parser):
        parser.add_argument('--once',action='store_true',help='Process at most one available job and exit.')
        parser.add_argument('--poll-seconds',type=float,default=2.0)
        parser.add_argument('--stale-minutes',type=int,default=10)
        parser.add_argument('--max-attempts',type=int,default=1,help='Maximum automatic attempts per analysis job.')
    def handle(self,*args,**opts):
        poll=max(.25,opts['poll_seconds']); stale=max(1,opts['stale_minutes']);max_attempts=max(1,opts['max_attempts'])
        while True:
            cutoff=timezone.now()-timedelta(minutes=stale)
            with transaction.atomic():
                stuck=list(AnalysisRun.objects.filter(state='processing',started_at__lt=cutoff).select_related('version__asset'))
                for run in stuck:
                    run.state='queued';run.save(update_fields=['state'])
                    run.version.asset.status='queued';run.version.asset.save(update_fields=['status'])
            job=AnalysisRun.objects.filter(state='queued').order_by('id').first()
            if job:
                try:
                    done=process_analysis_run(job.id)
                except Exception as exc:
                    with transaction.atomic():
                        failed=AnalysisRun.objects.select_related('version__asset').get(id=job.id)
                        failed.state='failed';failed.errors=[f'Worker failure ({type(exc).__name__}).'];failed.finished_at=timezone.now();failed.save(update_fields=['state','errors','finished_at'])
                        failed.version.asset.status='failed';failed.version.asset.save(update_fields=['status'])
                    done=failed;self.stderr.write(f'Analysis run {job.id} failed on attempt {failed.attempts} ({type(exc).__name__}).')
                if done.state=='failed' and done.attempts<max_attempts:
                    with transaction.atomic():
                        retry=AnalysisRun.objects.select_related('version__asset').get(id=done.id)
                        retry.state='queued';retry.finished_at=None;retry.save(update_fields=['state','finished_at'])
                        retry.version.asset.status='queued';retry.version.asset.save(update_fields=['status'])
                    self.stderr.write(f'Retrying analysis run {done.id} (attempt {done.attempts+1} of {max_attempts}).')
                    time.sleep(min(2**max(0,done.attempts-1),30))
                    continue
                self.stdout.write(f'Analysis run {done.id}: {done.state} (attempt {done.attempts})')
                if opts['once']:return
            elif opts['once']:
                self.stdout.write('No queued analysis jobs.');return
            else:time.sleep(poll)
