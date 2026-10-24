from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from app.models import Workspace, Membership, Guideline, Rule, ApprovedExample, EvidenceSource, BrandPaletteEntry, ReferenceLogo, Asset, AssetVersion, AnalysisRun, Review, Finding, Comment, AuditEvent, GuidelineVersion
from app.views import analyze, deterministic_claim_triage, sync_guideline_chunks, run_visual_checks
import hashlib

class Command(BaseCommand):
    help='Create a clearly labeled BrandProof demo workspace using the same deterministic analysis pipeline.'
    def add_arguments(self, parser):
        parser.add_argument('--username',default='brandproof-demo')
        parser.add_argument('--password',required=True,help='Choose a local demo password; it will not be printed.')
    @transaction.atomic
    def handle(self,*args,**options):
        username=options['username']; password=options['password']
        user,created=User.objects.get_or_create(username=username)
        user.set_password(password); user.save()
        workspace,_=Workspace.objects.get_or_create(name='DEMO — Verdant House')
        Membership.objects.update_or_create(workspace=workspace,user=user,defaults={'role':'admin'})
        if workspace.guidelines.exists():
            raise CommandError('Demo workspace already contains guidelines. Remove the demo workspace data before seeding again.')
        guide=Guideline.objects.create(workspace=workspace,name='DEMO — Verdant House voice',source_text='[Page 1]\nUse warm, clear language that respects the reader. Avoid unsupported superlatives and guarantees. Prefer specific, evidence-backed statements over broad numerical claims.')
        Rule.objects.create(guideline=guide,title='Avoid “cheap”',text='cheap',category='prohibited',severity='high',replacement='thoughtful value')
        Rule.objects.create(guideline=guide,title='Use “members”',text='users',category='preferred',severity='low',replacement='members')
        Rule.objects.create(guideline=guide,title='Review absolute claims',text='Avoid unsupported superlatives and guarantees.',category='claim',severity='medium')
        ApprovedExample.objects.create(guideline=guide,text='DEMO approved: A calmer way to plan your work.',approved=True)
        ApprovedExample.objects.create(guideline=guide,text='DEMO disallowed: The best productivity tool, guaranteed.',approved=False)
        EvidenceSource.objects.create(workspace=workspace,name='DEMO — Product fact sheet',source_type='internal',passage='Demonstration source: the fact sheet contains no verified customer-count statistic.',approved=True)
        BrandPaletteEntry.objects.create(workspace=workspace,name='DEMO — Verdant green',hex_value='#456B50')
        GuidelineVersion.objects.create(guideline=guide,number=1,created_by=user,snapshot={'demo':True,'name':guide.name,'rules':[{'title':r.title,'text':r.text,'category':r.category} for r in guide.rules.all()]})
        sync_guideline_chunks(guide)
        original='The cheap productivity suite for users. Trusted by 99,999 teams — the best way to do your work.'
        corrected='A thoughtful-value productivity suite for members. Explore a calmer way to do your work.'
        asset=Asset.objects.create(workspace=workspace,title='DEMO — Spring launch landing page',campaign='DEMO — Spring launch',created_by=user)
        v1=AssetVersion.objects.create(asset=asset,number=1,content=original,extracted_text=original,content_hash=hashlib.sha256(original.encode()).hexdigest(),created_by=user)
        AnalysisRun.objects.create(version=v1,state='processing'); analyze(v1,workspace)
        if not v1.claims.exists():deterministic_claim_triage(v1)
        AnalysisRun.objects.filter(version=v1).update(state='warnings',warnings=['DEMO data. Deterministic checks only; no external AI inference was run. Numerical claim remains unverified without an evidence match.'])
        Review.objects.create(version=v1,state='changes_requested',reviewer=user,reason='DEMO review: replace the prohibited wording and provide approved evidence for the numerical claim.')
        for index in range(3):
            sample=f'DEMO — Review signal {index+1}'
            extra=Asset.objects.create(workspace=workspace,title=sample,created_by=user)
            version=AssetVersion.objects.create(asset=extra,number=1,content='A cheap offer.',extracted_text='A cheap offer.',content_hash=hashlib.sha256((sample+'cheap').encode()).hexdigest(),created_by=user)
            analyze(version,workspace)
            extra.status='warnings';extra.save(update_fields=['status'])
            AnalysisRun.objects.create(version=version,state='warnings',warnings=['DEMO data. Deterministic checks only; no LLM inference was run.'])
            for finding in version.findings.filter(rule__category='prohibited'):
                finding.status='dismissed';finding.save(update_fields=['status'])
                Comment.objects.create(finding=finding,author=user,body='DEMO reviewer signal: scope of this rule needs clarification.')
        asset.latest_version=2;asset.status='warnings';asset.save(update_fields=['latest_version','status'])
        v2=AssetVersion.objects.create(asset=asset,number=2,content=corrected,extracted_text=corrected,content_hash=hashlib.sha256(corrected.encode()).hexdigest(),created_by=user)
        AnalysisRun.objects.create(version=v2,state='warnings',warnings=['DEMO data. Local deterministic checks only; AI analysis was not run.'])
        analyze(v2,workspace)
        Review.objects.create(version=v2,state='approved',reviewer=user,reason='DEMO approval of version 2; approval applies only to this exact version.')
        from io import BytesIO
        from PIL import Image,ImageDraw
        from django.core.files.base import ContentFile
        logo_image=Image.new('RGB',(40,40),'white');draw=ImageDraw.Draw(logo_image);draw.ellipse((4,4,36,36),fill='#1B3D2A');draw.ellipse((12,9,28,27),fill='#A8B99C')
        logo_buffer=BytesIO();logo_image.save(logo_buffer,format='PNG')
        reference=ReferenceLogo(workspace=workspace,name='DEMO — Verdant emblem');reference.image.save('demo-verdant-emblem.png',ContentFile(logo_buffer.getvalue()));reference.save()
        banner=Image.new('RGB',(240,140),'#F3F0E7');banner.paste(logo_image,(18,18));ImageDraw.Draw(banner).text((76,39),'VERDANT HOUSE',fill='#26352A')
        banner_buffer=BytesIO();banner.save(banner_buffer,format='PNG')
        visual_asset=Asset.objects.create(workspace=workspace,title='DEMO — Spring campaign visual',campaign='DEMO — Spring launch',created_by=user,status='warnings')
        visual_asset.source_file.save('demo-spring-campaign.png',ContentFile(banner_buffer.getvalue()),save=True)
        visual_text='DEMO — Spring campaign visual. OCR may be unavailable; image color and logo checks are advisory.'
        visual_version=AssetVersion.objects.create(asset=visual_asset,number=1,content=visual_text,extracted_text=visual_text,extraction_method='demo_image',extraction_status='warnings',extraction_warnings=['DEMO visual sample. OCR is not claimed to have run.'],content_hash=hashlib.sha256(banner_buffer.getvalue()).hexdigest(),created_by=user)
        AnalysisRun.objects.create(version=visual_version,state='warnings',warnings=['DEMO visual sample. Color and logo results are advisory; OCR was not run by the seeder.'])
        visual_warnings=run_visual_checks(visual_version,workspace)
        AuditEvent.objects.create(workspace=workspace,actor=user,action='demo_visual_asset_created',details={'asset_id':visual_asset.id,'warnings':visual_warnings})
        AuditEvent.objects.create(workspace=workspace,actor=user,action='demo_seeded',details={'label':'DEMO','asset_id':asset.id,'versions':[1,2]})
        self.stdout.write(self.style.SUCCESS(f'DEMO workspace ready. Sign in as {username} with the password supplied to this command.'))
