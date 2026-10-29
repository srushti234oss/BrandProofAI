from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from .models import Workspace, Membership, Guideline, Rule, Asset, AssetVersion, Finding, Review, ExtractedClaim, Comment, AuditEvent, AnalysisRun
class BrandProofApiTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='reviewer',password='a-long-test-password')
        self.workspace=Workspace.objects.create(name='Test brand')
        Membership.objects.create(workspace=self.workspace,user=self.user,role='admin')
        self.client=APIClient(); self.client.force_authenticate(self.user)
    def finish_asset(self,response):
        from .models import AnalysisRun
        from .views import process_analysis_run
        self.assertEqual(response.status_code,202)
        run=AnalysisRun.objects.get(version__asset_id=response.data['id'],version__number=response.data['latest_version'])
        process_analysis_run(run.id)
        return next(row for row in self.client.get(f'/api/v1/workspaces/{self.workspace.id}/assets/').data if row['id']==response.data['id'])
    def test_synthetic_evaluation_dataset_has_labelled_claim_and_visual_cases(self):
        import json
        from pathlib import Path
        dataset=json.loads((Path(__file__).parent/'evaluation_cases.json').read_text())
        self.assertTrue(dataset['synthetic'])
        self.assertGreaterEqual(len(dataset['claim_cases']),10)
        self.assertGreaterEqual(len(dataset['visual_cases']),8)
        self.assertEqual({row['expected'] for row in dataset['claim_cases'] if row['id'].startswith('claim-')}&{'supported','contradicted','unverified','uncertain'},{'supported','contradicted','unverified','uncertain'})
    def test_workspace_scoped_dashboard(self):
        res=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/dashboard/')
        self.assertEqual(res.status_code,200); self.assertEqual(res.data['total_assets'],0)
        self.assertEqual(self.client.get('/api/v1/workspaces/9999/dashboard/').status_code,404)
    def test_end_to_end_register_guideline_evidence_review_and_receipt(self):
        client=APIClient()
        registered=client.post('/api/v1/auth/',{'action':'register','username':'journey-user','password':'A-strong-test-password-2026'},format='json')
        self.assertEqual(registered.status_code,200)
        workspace=client.post('/api/v1/workspaces/',{'name':'Journey Brand'},format='json')
        self.assertEqual(workspace.status_code,201)
        wid=workspace.data['id']
        guideline=client.post(f'/api/v1/workspaces/{wid}/guidelines/',{'name':'Journey rules','source_text':'Use careful claims.','rule_title':'Avoid guaranteed','rule_text':'guaranteed','rule_category':'prohibited'},format='json')
        self.assertEqual(guideline.status_code,201)
        evidence=client.post(f'/api/v1/workspaces/{wid}/evidence/',{'name':'Approved product brief','passage':'BrightBite contains oats.','approved':True,'source_type':'internal'},format='json')
        self.assertEqual(evidence.status_code,201)
        submitted=client.post(f'/api/v1/workspaces/{wid}/assets/',{'title':'Journey social post','campaign':'Journey','content':'BrightBite is guaranteed to delight. It contains oats.'},format='json')
        self.assertEqual(submitted.status_code,202)
        from .views import process_analysis_run
        run=AnalysisRun.objects.get(version__asset_id=submitted.data['id'])
        process_analysis_run(run.id)
        checked=client.get(f'/api/v1/workspaces/{wid}/assets/')
        self.assertEqual(checked.status_code,200)
        reviewed_asset=next(item for item in checked.data if item['id']==submitted.data['id'])
        self.assertTrue(reviewed_asset['version']['findings'])
        decision=client.post(f'/api/v1/workspaces/{wid}/assets/{submitted.data["id"]}/review/',{'state':'submitted'},format='json')
        self.assertEqual(decision.status_code,201)
        receipt=client.get(f'/api/v1/workspaces/{wid}/assets/{submitted.data["id"]}/receipt/')
        self.assertEqual(receipt.status_code,200)
        self.assertEqual(receipt.data['decision'],'submitted')
        self.assertEqual(receipt.data['analysis_state'],'warnings')
    def test_asset_submission_rejects_non_text_fields_without_server_error(self):
        response=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':['not','text'],'content':'Some copy'},format='json')
        self.assertEqual(response.status_code,400)
        self.assertIn('must be text',response.data['error'])
        self.assertEqual(Asset.objects.count(),0)
    def test_repeating_review_decision_is_idempotent(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Repeat decision',created_by=self.user)
        AssetVersion.objects.create(asset=asset,number=1,content='Copy',extracted_text='Copy',content_hash='9'*64,created_by=self.user)
        path=f'/api/v1/workspaces/{self.workspace.id}/assets/{asset.id}/review/'
        first=self.client.post(path,{'state':'submitted'},format='json')
        second=self.client.post(path,{'state':'submitted'},format='json')
        self.assertEqual(first.status_code,201)
        self.assertEqual(second.status_code,200)
        self.assertTrue(second.data['duplicate'])
        self.assertEqual(Review.objects.count(),1)
    def test_repeating_retry_returns_existing_queued_job(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Retry once',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='Copy',extracted_text='Copy',content_hash='8'*64,created_by=self.user)
        AnalysisRun.objects.create(version=version,state='failed')
        path=f'/api/v1/workspaces/{self.workspace.id}/assets/{asset.id}/retry-analysis/'
        first=self.client.post(path,{},format='json')
        second=self.client.post(path,{},format='json')
        self.assertEqual(first.status_code,202)
        self.assertEqual(second.status_code,202)
        self.assertTrue(second.data['duplicate'])
        self.assertEqual(AnalysisRun.objects.filter(version=version).count(),2)
    def test_campaign_consistency_flags_repeated_sentence_with_changed_numbers(self):
        from .models import AssetVersion
        for title,campaign,text in [('Landing page','Spring 2026','Get 24-hour hydration support.'),('Social post','spring 2026','Get 72-hour hydration support.')]:
            asset=Asset.objects.create(workspace=self.workspace,title=title,campaign=campaign,created_by=self.user)
            AssetVersion.objects.create(asset=asset,number=1,content=text,extracted_text=text,content_hash=title.lower().replace(' ','0')[:64].ljust(64,'a'),created_by=self.user)
        response=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/campaigns/consistency/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.data['campaigns']),1)
        campaign=response.data['campaigns'][0]
        self.assertEqual(campaign['asset_count'],2)
        self.assertEqual(campaign['conflict_count'],1)
        self.assertEqual(campaign['conflicts'][0]['left']['numbers'],['24'])
        self.assertEqual(campaign['conflicts'][0]['right']['numbers'],['72'])
    def test_campaign_consistency_does_not_flag_same_value_or_different_workspaces(self):
        from .models import AssetVersion
        for title,text in [('A','Get 24-hour hydration support.'),('B','Get 24-hour hydration support.')]:
            asset=Asset.objects.create(workspace=self.workspace,title=title,campaign='Summer',created_by=self.user)
            AssetVersion.objects.create(asset=asset,number=1,content=text,extracted_text=text,content_hash=(title.lower()*64)[:64],created_by=self.user)
        other=Workspace.objects.create(name='Other')
        other_user=User.objects.create_user(username='other-reviewer',password='a-long-test-password')
        Membership.objects.create(workspace=other,user=other_user,role='admin')
        outside=Asset.objects.create(workspace=other,title='Outside',campaign='Summer',created_by=other_user)
        AssetVersion.objects.create(asset=outside,number=1,content='Get 99-hour hydration support.',extracted_text='Get 99-hour hydration support.',content_hash='c'*64,created_by=other_user)
        response=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/campaigns/consistency/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['campaigns'][0]['conflict_count'],0)
    def test_campaign_consistency_flags_disclaimer_and_preferred_wording_mismatches(self):
        guide=Guideline.objects.create(workspace=self.workspace,name='Approved wording')
        Rule.objects.create(guideline=guide,title='Preferred phrase',text='eco friendly',replacement='environmentally considerate',category='preferred')
        copies=[('Landing page','Get an eco friendly clean. Terms and conditions apply.'),('Social post','Get an environmentally considerate clean.')]
        for index,(title,text) in enumerate(copies):
            asset=Asset.objects.create(workspace=self.workspace,title=title,campaign='Summer launch',created_by=self.user)
            AssetVersion.objects.create(asset=asset,number=1,content=text,extracted_text=text,content_hash=hex(index+10)[2:]*64,created_by=self.user)
        response=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/campaigns/consistency/')
        self.assertEqual(response.status_code,200)
        conflicts=response.data['campaigns'][0]['conflicts']
        self.assertEqual({item['type'] for item in conflicts},{'preferred_wording_mismatch','disclaimer_presence_mismatch'})
    def test_upload_runs_explicit_rule_checks_and_claims_unverified(self):
        guide=Guideline.objects.create(workspace=self.workspace,name='Voice')
        Rule.objects.create(guideline=guide,title='Avoid cheap',text='cheap',category='prohibited')
        submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Campaign','content':'This is a cheap offer. We served 20,000 customers.'},format='json')
        res=self.finish_asset(submitted)
        self.assertEqual(res['status'],'warnings')
        self.assertTrue(any('not configured' in warning for warning in res['warnings']))
        kinds=set(Finding.objects.filter(version__asset_id=res['id']).values_list('kind',flat=True))
        self.assertIn('terminology',kinds); self.assertIn('claim',kinds)
    def test_approval_is_bound_to_exact_version(self):
        a=Asset.objects.create(workspace=self.workspace,title='A',created_by=self.user)
        v1=AssetVersion.objects.create(asset=a,number=1,content='Original',extracted_text='Original',content_hash='a'*64,created_by=self.user)
        res=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/{a.id}/review/',{'state':'approved'},format='json')
        self.assertEqual(res.status_code,201); self.assertEqual(Review.objects.get().version_id,v1.id)
    def test_correction_creates_new_hash_and_preserves_prior_version_approval(self):
        a=Asset.objects.create(workspace=self.workspace,title='Versioned',created_by=self.user)
        v1=AssetVersion.objects.create(asset=a,number=1,content='Before',extracted_text='Before',content_hash='b'*64,created_by=self.user)
        Review.objects.create(version=v1,state='approved',reviewer=self.user)
        res=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/{a.id}/corrections/',{'content':'After'},format='json')
        self.assertEqual(res.status_code,202); self.assertEqual(res.data['number'],2)
        from .models import AnalysisRun
        from .views import process_analysis_run
        process_analysis_run(AnalysisRun.objects.get(version_id=res.data['id']).id)
        self.assertTrue(v1.reviews.filter(state='approved').exists())
        self.assertFalse(AssetVersion.objects.get(number=2).reviews.filter(state='approved').exists())
    def test_correction_of_uploaded_asset_is_not_overwritten_by_original_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Uploaded copy','file':SimpleUploadedFile('copy.txt',b'Original wording.','text/plain')},format='multipart')
        self.finish_asset(submitted)
        updated=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/{submitted.data["id"]}/corrections/',{'content':'Corrected wording.'},format='json')
        from .models import AnalysisRun
        from .views import process_analysis_run
        process_analysis_run(AnalysisRun.objects.get(version_id=updated.data['id']).id)
        current=AssetVersion.objects.get(id=updated.data['id'])
        self.assertEqual(current.content,'Corrected wording.')
        self.assertEqual(current.extracted_text,'Corrected wording.')
    def test_claim_ledger_never_marks_missing_evidence_as_false(self):
        submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Numbers','content':'Our service helped 50,000 customers.'},format='json')
        response=self.finish_asset(submitted)
        claim=ExtractedClaim.objects.get(version__asset_id=response['id'])
        self.assertEqual(claim.classification,'unverified')
        self.assertEqual(self.client.get(f'/api/v1/workspaces/{self.workspace.id}/claims/').data[0]['classification'],'unverified')
    def test_clarity_requires_real_signal_threshold(self):
        guide=Guideline.objects.create(workspace=self.workspace,name='Voice')
        rule=Rule.objects.create(guideline=guide,title='Tone',text='Be concise',category='tone')
        empty=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/clarity/')
        self.assertEqual(empty.data,[])
        asset=Asset.objects.create(workspace=self.workspace,title='Signal',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='x',extracted_text='x',content_hash='c'*64,created_by=self.user)
        for _ in range(3):
            f=Finding.objects.create(version=version,kind='tone',text='x',explanation='x',rule=rule,status='dismissed')
        rows=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/clarity/').data
        self.assertEqual(rows[0]['signal_count'],3)
        accepted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/clarity/',{'rule_id':rule.id,'decision':'accept'},format='json')
        self.assertEqual(accepted.status_code,200);self.assertEqual(accepted.data['guideline_version'],2)
        self.assertEqual(rule.insights.get().state,'accepted')
        self.assertEqual(self.client.get(f'/api/v1/workspaces/{self.workspace.id}/clarity/').data,[])
    def test_configured_ai_source_ids_are_validated_and_unverified_claim_remains_unverified(self):
        from unittest.mock import patch
        from .views import run_configured_ai
        from .models import EvidenceSource
        approved=EvidenceSource.objects.create(workspace=self.workspace,name='Approved brief',passage='Customers reached 50,000.',approved=True)
        asset=Asset.objects.create(workspace=self.workspace,title='AI test',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='x',extracted_text='Our product reached 50,000 customers.',content_hash='d'*64,created_by=self.user)
        payload={'claims':[{'wording':'Our product reached 50,000 customers.','classification':'Supported','evidence_ids':[approved.id],'explanation':'The approved brief states the same total.'},{'wording':'Our product is the best.','classification':'Supported','evidence_ids':[999999],'explanation':'No source returned.'}],'tone_findings':[]}
        with patch.dict('os.environ',{'LLM_API_KEY':'test','LLM_MODEL':'test'}), patch('app.ai.analyze',return_value=payload):
            run_configured_ai(version,self.workspace)
        self.assertEqual(list(version.claims.order_by('id').values_list('classification',flat=True)),['supported','unverified'])
        self.assertEqual(version.claims.first().references.first().source_id,approved.id)
    def test_approval_with_open_findings_requires_recorded_override_reason(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Needs review',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='x',extracted_text='x',content_hash='e'*64,created_by=self.user)
        Finding.objects.create(version=version,kind='claim',text='Claim',explanation='Unverified')
        path=f'/api/v1/workspaces/{self.workspace.id}/assets/{asset.id}/review/'
        denied=self.client.post(path,{'state':'approved'},format='json')
        self.assertEqual(denied.status_code,400)
        approved=self.client.post(path,{'state':'approved','reason':'We accept the remaining uncertainty.'},format='json')
        self.assertEqual(approved.status_code,201)
    def test_dashboard_counts_only_latest_version_approval(self):
        from .models import Review
        asset=Asset.objects.create(workspace=self.workspace,title='Updated after approval',created_by=self.user,latest_version=2)
        old=AssetVersion.objects.create(asset=asset,number=1,content='v1',extracted_text='v1',content_hash='1'*64,created_by=self.user)
        Review.objects.create(version=old,state='approved',reviewer=self.user)
        new=AssetVersion.objects.create(asset=asset,number=2,content='v2',extracted_text='v2',content_hash='2'*64,created_by=self.user)
        Review.objects.create(version=new,state='submitted',reviewer=self.user)
        data=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/dashboard/').data
        self.assertEqual(data['approved_assets'],0);self.assertEqual(data['awaiting_review'],1)
    def test_dismissing_finding_requires_reason_and_records_status_history(self):
        from .models import FindingStatusEvent
        asset=Asset.objects.create(workspace=self.workspace,title='Reason',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='x',extracted_text='x',content_hash='f'*64,created_by=self.user)
        finding=Finding.objects.create(version=version,kind='tone',text='x',explanation='x')
        path=f'/api/v1/workspaces/{self.workspace.id}/findings/{finding.id}/'
        denied=self.client.post(path,{'action':'status','status':'dismissed'},format='json')
        self.assertEqual(denied.status_code,400)
        ok=self.client.post(path,{'action':'status','status':'dismissed','reason':'Not applicable to a footnote.'},format='json')
        self.assertEqual(ok.status_code,200)
        self.assertEqual(FindingStatusEvent.objects.get().reason,'Not applicable to a footnote.')
    def test_trust_receipt_is_generated_for_persisted_version(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Receipt asset',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='Copy',extracted_text='Copy',content_hash='a'*64,created_by=self.user)
        res=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/assets/{asset.id}/receipt/')
        self.assertEqual(res.status_code,200); self.assertEqual(res.data['version_id'],version.id)
        self.assertEqual(res.data['content_hash'],'a'*64); self.assertEqual(res.data['decision'],'No final decision recorded')
    def test_source_download_is_authenticated_and_workspace_scoped(self):
        from django.core.files.base import ContentFile
        asset=Asset.objects.create(workspace=self.workspace,title='Private original',created_by=self.user)
        asset.source_file.save('original.txt',ContentFile(b'private brand content'),save=True)
        try:
            response=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/source-files/asset/{asset.id}/')
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response['Content-Disposition'])
            self.assertEqual(b''.join(response.streaming_content),b'private brand content')
            other=Workspace.objects.create(name='Other workspace')
            self.assertEqual(self.client.get(f'/api/v1/workspaces/{other.id}/source-files/asset/{asset.id}/').status_code,404)
        finally:
            asset.source_file.delete(save=False)

    def test_configured_smtp_sends_invitation_email(self):
        from unittest.mock import patch
        from django.test import override_settings
        with override_settings(EMAIL_HOST='smtp.example.test',DEFAULT_FROM_EMAIL='proof@example.test',PUBLIC_APP_URL='https://brand.example.test'):
            with patch('app.views.send_mail',return_value=1) as send:
                response=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/invitations/',{'email':'invited@example.test','role':'reviewer'},format='json')
        self.assertEqual(response.status_code,201)
        self.assertTrue(response.data['email_sent'])
        self.assertIn('https://brand.example.test/?invite=',send.call_args.args[1])

    def test_audit_endpoint_returns_only_the_current_workspaces_events(self):
        other=Workspace.objects.create(name='Private other brand')
        AuditEvent.objects.create(workspace=self.workspace,actor=self.user,action='review_submitted',details={'asset':7})
        AuditEvent.objects.create(workspace=other,actor=self.user,action='must_not_leak',details={})
        response=self.client.get(f'/api/v1/workspaces/{self.workspace.id}/audit/')
        self.assertEqual(response.status_code,200)
        self.assertEqual([event['action'] for event in response.data],['review_submitted'])

    def test_receipt_can_select_version_and_includes_diff_and_decisions(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Versioned receipt',created_by=self.user,latest_version=2)
        first=AssetVersion.objects.create(asset=asset,number=1,content='Original wording.',extracted_text='Original wording.',content_hash='1'*64,created_by=self.user)
        AssetVersion.objects.create(asset=asset,number=2,content='Updated wording.',extracted_text='Updated wording.',content_hash='2'*64,created_by=self.user)
        Review.objects.create(version=first,state='changes_requested',reviewer=self.user,reason='Clarify the claim.')
        second=asset.versions.get(number=2)
        Review.objects.create(version=second,state='approved',reviewer=self.user)
        base=f'/api/v1/workspaces/{self.workspace.id}/assets/{asset.id}/receipt/'
        response=self.client.get(base+'?version=2')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['version'],2)
        self.assertEqual(response.data['decision'],'approved')
        self.assertEqual(response.data['correction_from_version'],1)
        self.assertTrue(any(line.startswith('-Original') for line in response.data['corrections_applied']))
        self.assertTrue(any(line.startswith('+Updated') for line in response.data['corrections_applied']))
        old=self.client.get(base+'?version=1')
        self.assertEqual(old.data['decision'],'changes_requested')
        self.assertEqual(old.data['content_hash'],'1'*64)

    def test_demo_seed_uses_labeled_records_and_creates_clarity_signal(self):
        from django.core.management import call_command
        from django.contrib.auth.models import User
        call_command('seed_demo',username='seed-test',password='ExamplePasswordLong!2026',verbosity=0)
        demo=Workspace.objects.get(name='DEMO — Verdant House')
        self.assertTrue(demo.assets.filter(title__startswith='DEMO').exists())
        self.assertTrue(demo.guidelines.filter(name__startswith='DEMO').exists())
        self.assertEqual(Membership.objects.get(user__username='seed-test').role,'admin')
        self.assertTrue(demo.assets.get(title='DEMO — Spring launch landing page').versions.filter(number=2).exists())
    def test_visual_module_returns_advisory_palette_and_logo_confidence(self):
        from io import BytesIO
        from tempfile import TemporaryDirectory
        from PIL import Image, ImageDraw
        from django.core.files.base import ContentFile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from .models import BrandPaletteEntry, ReferenceLogo
        from .views import assets
        logo=Image.new('RGB',(32,32),'white'); draw=ImageDraw.Draw(logo)
        for x in range(0,32,8):
            for y in range(0,32,8):
                if (x//8+y//8)%2==0:draw.rectangle((x,y,x+7,y+7),fill='#1B3D2A')
        logo_bytes=BytesIO();logo.save(logo_bytes,format='PNG')
        banner=Image.new('RGB',(160,96),'#e8ece6');banner.paste(logo,(56,32));banner_bytes=BytesIO();banner.save(banner_bytes,format='PNG')
        with TemporaryDirectory() as temp, override_settings(MEDIA_ROOT=temp):
            palette=BrandPaletteEntry.objects.create(workspace=self.workspace,name='Leaf green',hex_value='#1B3D2A')
            reference=ReferenceLogo(workspace=self.workspace,name='Leaf mark');reference.image.save('reference.png',ContentFile(logo_bytes.getvalue()));reference.save()
            upload=SimpleUploadedFile('campaign.png',banner_bytes.getvalue(),content_type='image/png')
            from unittest.mock import patch
            ocr={'method':'tesseract_ocr','image_size':{'width':160,'height':96},'ocr_confidence':88.0,'ocr_regions':[{'text':'banner','x':2,'y':2,'width':45,'height':18,'confidence':88.0}]}
            with patch('app.views.image_checks',return_value=('banner',[],ocr)):
                submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Image test','file':upload},format='multipart')
                response=self.finish_asset(submitted)
            visual=Finding.objects.filter(version__asset_id=response['id'],kind='visual_logo_match').first()
            self.assertIsNotNone(visual,msg=str(response.get('warnings')));self.assertEqual(visual.location['x'],56);self.assertEqual(visual.location['y'],32)
            version=AssetVersion.objects.get(pk=visual.version_id)
            self.assertEqual(version.extraction_metadata.get('ocr_confidence'),88.0,msg=str(version.extraction_metadata))
            self.assertTrue(Finding.objects.filter(version=visual.version,kind='visual_palette_advisory').exists())
    def test_comment_replies_remain_scoped_to_their_finding(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Comments',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='x',extracted_text='x',content_hash='3'*64,created_by=self.user)
        first=Finding.objects.create(version=version,kind='tone',text='x',explanation='x')
        other=Finding.objects.create(version=version,kind='tone',text='y',explanation='y')
        parent=Comment.objects.create(finding=first,author=self.user,body='Review this')
        path=f'/api/v1/workspaces/{self.workspace.id}/findings/{other.id}/'
        denied=self.client.post(path,{'action':'comment','body':'Reply','parent_id':parent.id},format='json')
        self.assertEqual(denied.status_code,400)
        ok=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/findings/{first.id}/',{'action':'comment','body':'Reply','parent_id':parent.id},format='json')
        self.assertEqual(ok.status_code,200);self.assertEqual(ok.data['comments'][0]['replies'][0]['body'],'Reply')
    def test_browser_registration_flow_issues_and_accepts_csrf_token(self):
        client=APIClient(enforce_csrf_checks=True)
        origin='http://localhost:5173'
        initial=client.get('/api/v1/auth/',HTTP_ORIGIN=origin)
        token=client.cookies['csrftoken'].value
        response=client.post('/api/v1/auth/',{'action':'register','username':'browser-user','password':'LongUniquePass!982'},format='json',HTTP_ORIGIN=origin,HTTP_X_CSRFTOKEN=token)
        self.assertEqual(initial.status_code,200);self.assertEqual(response.status_code,200)
        rotated=client.cookies['csrftoken'].value
        workspace=client.post('/api/v1/workspaces/',{'name':'Browser workspace'},format='json',HTTP_ORIGIN=origin,HTTP_X_CSRFTOKEN=rotated)
        self.assertEqual(workspace.status_code,201)
    def test_login_accepts_the_email_label_shown_by_the_signin_form(self):
        self.user.email='reviewer@example.test';self.user.save(update_fields=['email'])
        client=APIClient()
        response=client.post('/api/v1/auth/',{'action':'login','username':'REVIEWER@example.test','password':'a-long-test-password'},format='json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['user'],'reviewer')
    def test_workspace_admin_can_assign_roles_but_cannot_remove_last_admin(self):
        from .models import Membership
        path=f'/api/v1/workspaces/{self.workspace.id}/members/'
        last_admin=Membership.objects.get(workspace=self.workspace,user=self.user)
        denied=self.client.delete(f'{path}{last_admin.id}/')
        self.assertEqual(denied.status_code,400)
        other=User.objects.create_user(username='creator',password='LongUniquePass!982')
        added=self.client.post(path,{'username':other.username,'role':'reviewer'},format='json')
        self.assertEqual(added.status_code,201);self.assertEqual(added.data['role'],'reviewer')
        changed=self.client.patch(f'{path}{added.data["id"]}/',{'role':'manager'},format='json')
        self.assertEqual(changed.status_code,200);self.assertEqual(changed.data['role'],'manager')
    def test_lexical_retrieval_is_relevant_approved_and_workspace_scoped(self):
        from .models import EvidenceSource
        from .retrieval import retrieve_evidence
        other=Workspace.objects.create(name='Other company')
        relevant=EvidenceSource.objects.create(workspace=self.workspace,name='Customer count',passage='The pilot served 500 customers.',approved=True)
        EvidenceSource.objects.create(workspace=self.workspace,name='Unrelated',passage='Seasonal colors and logo rules.',approved=True)
        EvidenceSource.objects.create(workspace=self.workspace,name='Unapproved data',passage='Pilot served 500 customers.',approved=False)
        EvidenceSource.objects.create(workspace=other,name='Cross workspace',passage='Pilot served 500 customers.',approved=True)
        self.assertEqual(retrieve_evidence(self.workspace,'The pilot served 500 customers.'),[relevant])
        self.assertEqual(retrieve_evidence(self.workspace,'Nebula zebra 827.'),[])
    def test_guideline_can_be_edited_as_a_new_version_and_image_is_rejected(self):
        guide=Guideline.objects.create(workspace=self.workspace,name='Voice',source_text='Old text')
        path=f'/api/v1/workspaces/{self.workspace.id}/guidelines/{guide.id}/'
        result=self.client.patch(path,{'name':'Voice v2','source_text':'Updated policy'},format='json')
        self.assertEqual(result.status_code,200);self.assertEqual(result.data['version'],2)
        self.assertTrue(guide.versions.filter(number=2,snapshot__source_text='Updated policy').exists())
        self.assertTrue(guide.chunks.filter(version=2,text__icontains='Updated policy').exists())
        from django.core.files.uploadedfile import SimpleUploadedFile
        rejected=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/guidelines/',{'name':'Bad image','file':SimpleUploadedFile('guide.png',b'not really png','image/png')},format='multipart')
        self.assertEqual(rejected.status_code,400)
    def test_text_upload_persists_extraction_method_and_warnings(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Text file','file':SimpleUploadedFile('copy.txt',b'Our service served 42 teams.','text/plain')},format='multipart')
        response=self.finish_asset(submitted)
        self.assertEqual(response['version']['extraction_method'],'plain_text')
        self.assertEqual(response['version']['extraction_status'],'completed')
        from .models import AnalysisRun
        run=AnalysisRun.objects.get(version_id=response['version']['id'])
        self.assertIsNotNone(run.started_at);self.assertIsNotNone(run.finished_at)
    def test_generated_api_schema_is_available_without_login(self):
        response=APIClient().get('/api/schema/')
        self.assertEqual(response.status_code,200)
        self.assertIn('/api/v1/workspaces/',response.data['paths'])
    def test_claim_ledger_search_and_filters_are_workspace_scoped(self):
        submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Filtered','content':'Our pilot served 42 customer teams.'},format='json')
        self.finish_asset(submitted)
        base=f'/api/v1/workspaces/{self.workspace.id}/claims/'
        self.assertEqual(len(self.client.get(base,{'q':'42','classification':'unverified','category':'promotional','status':'open','severity':'medium'}).data),1)
        self.assertEqual(self.client.get(base,{'q':'no-match'}).data,[])
    def test_durable_worker_marks_corrupt_upload_failed_and_allows_retry(self):
        from django.core.management import call_command
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import AnalysisRun
        response=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Corrupt PDF','file':SimpleUploadedFile('broken.pdf',b'not a PDF','application/pdf')},format='multipart')
        self.assertEqual(response.status_code,202);self.assertEqual(response.data['status'],'queued')
        first=AnalysisRun.objects.get(version__asset_id=response.data['id'])
        self.assertEqual(first.state,'queued')
        call_command('run_analysis_worker',once=True,verbosity=0)
        first.refresh_from_db();self.assertEqual(first.state,'failed');self.assertIsNotNone(first.finished_at)
        retry=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/{response.data["id"]}/retry-analysis/',{},format='json')
        self.assertEqual(retry.status_code,202);self.assertEqual(retry.data['state'],'queued')
    def test_worker_automatically_retries_failed_job_up_to_configured_limit(self):
        from django.core.management import call_command
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch
        response=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Retry corrupt PDF','file':SimpleUploadedFile('broken.pdf',b'not a PDF','application/pdf')},format='multipart')
        with patch('app.management.commands.run_analysis_worker.time.sleep'):
            call_command('run_analysis_worker',once=True,max_attempts=3,verbosity=0)
        run=AnalysisRun.objects.get(version__asset_id=response.data['id'])
        self.assertEqual(run.state,'failed')
        self.assertEqual(run.attempts,3)
        self.assertEqual(run.version.asset.status,'failed')
    def test_workspace_invitation_is_single_use_and_assigns_invited_role(self):
        from urllib.parse import urlparse,parse_qs
        invite=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/invitations/',{'email':'new-member@example.test','role':'reviewer'},format='json')
        self.assertEqual(invite.status_code,201)
        token=parse_qs(urlparse(invite.data['invite_path']).query)['invite'][0]
        joining=APIClient().post('/api/v1/auth/',{'action':'register','username':'invited-reviewer','password':'A-Strong-Invite-Pass-492!','invite_token':token},format='json')
        self.assertEqual(joining.status_code,200)
        self.assertEqual(Membership.objects.get(user__username='invited-reviewer',workspace=self.workspace).role,'reviewer')
        reused=APIClient().post('/api/v1/auth/',{'action':'register','username':'second-user','password':'Another-Strong-Pass-93!','invite_token':token},format='json')
        self.assertEqual(reused.status_code,400)
    def test_findings_can_only_be_assigned_to_workspace_reviewers(self):
        asset=Asset.objects.create(workspace=self.workspace,title='Assignment',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='Copy',extracted_text='Copy',content_hash='7'*64,created_by=self.user)
        finding=Finding.objects.create(version=version,kind='tone',text='Copy',explanation='Check tone')
        reviewer=User.objects.create_user(username='reviewer-two',password='A-Strong-Reviewer-Pass-392!')
        Membership.objects.create(workspace=self.workspace,user=reviewer,role='reviewer')
        path=f'/api/v1/workspaces/{self.workspace.id}/findings/{finding.id}/'
        response=self.client.post(path,{'action':'assign','user_id':reviewer.id},format='json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['assigned_to'],'reviewer-two')
    def test_optional_pagination_preserves_unpaginated_frontend_contract(self):
        submitted=self.client.post(f'/api/v1/workspaces/{self.workspace.id}/assets/',{'title':'Page','content':'We helped 42 teams.'},format='json')
        self.finish_asset(submitted)
        path=f'/api/v1/workspaces/{self.workspace.id}/claims/'
        self.assertIsInstance(self.client.get(path).data,list)
        page=self.client.get(path,{'page':1,'page_size':1})
        self.assertEqual(page.status_code,200);self.assertEqual(page.data['count'],1);self.assertEqual(len(page.data['results']),1)
    def test_retention_policy_and_purge_command_are_audited(self):
        from django.core.management import call_command
        from django.utils import timezone
        from datetime import timedelta
        path=f'/api/v1/workspaces/{self.workspace.id}/settings/'
        changed=self.client.patch(path,{'retention_days':1},format='json')
        self.assertEqual(changed.status_code,200);self.assertEqual(changed.data['retention_days'],1)
        asset=Asset.objects.create(workspace=self.workspace,title='Expired',created_by=self.user)
        Asset.objects.filter(id=asset.id).update(created_at=timezone.now()-timedelta(days=2))
        call_command('purge_expired_assets',dry_run=True,verbosity=0)
        self.assertTrue(Asset.objects.filter(id=asset.id).exists())
        call_command('purge_expired_assets',verbosity=0)
        self.assertFalse(Asset.objects.filter(id=asset.id).exists())
        self.assertTrue(AuditEvent.objects.filter(workspace=self.workspace,action='retention_assets_purged').exists())
    def test_embedding_retrieval_ranks_only_approved_workspace_vectors(self):
        from .models import EvidenceSource
        from .retrieval import retrieve_evidence_with_embeddings
        other=Workspace.objects.create(name='Vector isolation')
        best=EvidenceSource.objects.create(workspace=self.workspace,name='Relevant',passage='relevant',approved=True,embedding=[0.98,0.1],embedding_model='test-embed')
        EvidenceSource.objects.create(workspace=self.workspace,name='Poor match',passage='other',approved=True,embedding=[0.1,0.98],embedding_model='test-embed')
        lexical=EvidenceSource.objects.create(workspace=self.workspace,name='claim source',passage='claim wording',approved=True,embedding=[0.1,0.98],embedding_model='test-embed')
        EvidenceSource.objects.create(workspace=self.workspace,name='Unapproved',passage='x',approved=False,embedding=[1,0],embedding_model='test-embed')
        EvidenceSource.objects.create(workspace=other,name='Foreign',passage='x',approved=True,embedding=[1,0],embedding_model='test-embed')
        rows,method=retrieve_evidence_with_embeddings(self.workspace,'claim',[1,0],'test-embed')
        self.assertEqual(method,'embeddings_hybrid')
        self.assertIn(best,rows);self.assertIn(lexical,rows)
    def test_pgvector_candidate_is_rechecked_for_current_approval(self):
        from unittest.mock import patch
        from .models import EvidenceSource
        from .retrieval import retrieve_evidence_with_embeddings
        revoked=EvidenceSource.objects.create(workspace=self.workspace,name='Claim support',passage='claim data',approved=False,embedding=[1,0],embedding_model='test-embed')
        with patch('app.retrieval._pgvector_rows',return_value=[(revoked.id,0.99)]):
            rows,method=retrieve_evidence_with_embeddings(self.workspace,'claim',[1,0],'test-embed')
        self.assertEqual(rows,[])
        self.assertEqual(method,'embeddings_empty')
    def test_embedding_index_mirrors_json_vectors_for_portable_fallback(self):
        from .models import EvidenceSource, EmbeddingIndex
        from .retrieval import sync_embedding_index
        source=EvidenceSource.objects.create(workspace=self.workspace,name='Facts',passage='Fact passage',approved=True)
        sync_embedding_index(workspace=self.workspace,evidence_source=source,embedding=[0.25,0.75],model='test-embed')
        row=EmbeddingIndex.objects.get(evidence_source=source,embedding_model='test-embed')
        self.assertEqual(row.dimensions,2)
        self.assertEqual(row.embedding_json,[0.25,0.75])
    def test_configured_ai_uses_embedding_ranked_evidence(self):
        from unittest.mock import patch
        from .models import EvidenceSource
        from .views import run_configured_ai
        relevant=EvidenceSource.objects.create(workspace=self.workspace,name='Good',passage='Relevant',approved=True,embedding=[1.0,0.0],embedding_model='test-embed')
        EvidenceSource.objects.create(workspace=self.workspace,name='Other',passage='Unrelated',approved=True,embedding=[0.0,1.0],embedding_model='test-embed')
        asset=Asset.objects.create(workspace=self.workspace,title='Vector analysis',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='claim',extracted_text='claim',content_hash='4'*64,created_by=self.user)
        with patch.dict('os.environ',{'LLM_API_KEY':'test','LLM_MODEL':'test','LLM_EMBEDDING_MODEL':'test-embed'}), patch('app.ai.embed',return_value=[1.0,0.0]), patch('app.ai.analyze',return_value={'claims':[],'tone_findings':[]}) as provider:
            run_configured_ai(version,self.workspace)
        self.assertEqual([source.id for source in provider.call_args.args[2]],[relevant.id])
    def test_configured_ai_retrieves_and_persists_guideline_section_references(self):
        from unittest.mock import patch
        from .models import GuidelineChunk
        from .views import sync_guideline_chunks,run_configured_ai
        guide=Guideline.objects.create(workspace=self.workspace,name='Brand handbook',source_text='[Page 4]\nUse warm, specific wording for customer claims.')
        chunk=sync_guideline_chunks(guide)[0]
        asset=Asset.objects.create(workspace=self.workspace,title='Guideline RAG',created_by=self.user)
        version=AssetVersion.objects.create(asset=asset,number=1,content='Use warm, specific wording for customer claims.',extracted_text='Use warm, specific wording for customer claims.',content_hash='5'*64,created_by=self.user)
        payload={'claims':[{'wording':'customer claims','classification':'unverified','explanation':'Review the brand wording.','guideline_chunk_ids':[chunk.id]}],'tone_findings':[]}
        with patch.dict('os.environ',{'LLM_API_KEY':'test','LLM_MODEL':'test','LLM_EMBEDDING_MODEL':''}),patch('app.ai.analyze',return_value=payload) as provider:
            run_configured_ai(version,self.workspace)
        self.assertEqual(provider.call_args.args[3],[chunk])
        reference=version.claims.get().guideline_references.get()
        self.assertEqual(reference.chunk_id,chunk.id);self.assertEqual(reference.location,'Page 4')
    def test_evidence_document_upload_extracts_passage_and_parses_approval(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        path=f'/api/v1/workspaces/{self.workspace.id}/evidence/'
        response=self.client.post(path,{'name':'Uploaded brief','file':SimpleUploadedFile('brief.txt',b'The pilot supported 42 teams.','text/plain'),'approved':'true'},format='multipart')
        self.assertEqual(response.status_code,201)
        source=__import__('app.models',fromlist=['EvidenceSource']).EvidenceSource.objects.get(id=response.data['id'])
        self.assertTrue(source.approved);self.assertIn('42 teams',source.passage);self.assertTrue(source.source_file)
