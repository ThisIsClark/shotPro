import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from app.main import app
from app.config import settings
from app.api.deps import get_current_user_required, get_current_user_optional
from app.services import admin_insights as insights, admin_metrics as metrics
from app.services.trial_service import trial_store
from app.services.db_service import db_service
from app.services.feedback_service import feedback_store

class InsightsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patches=[patch.object(trial_store,'path',self.root/'trial.db'),patch.object(settings,'results_dir',self.root/'results'),patch.object(feedback_store,'root',self.root/'feedback'),patch.object(db_service,'is_available',return_value=False)]
        for p in self.patches:p.start()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://test')
        self.now=time.time()-100
    async def asyncTearDown(self):
        app.dependency_overrides.clear();await self.client.aclose()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def report(self, task='first', visitor='v', owner=None, created=10, phases=None):
        trial_store.reserve(task,visitor,owner,'shot.mov','hashed')
        metrics.quality(task,frames=8);trial_store.finish(task,True)
        insights.task_metadata(task,metadata={'template_id':'curry'},frames=[{'phase':k,'timestamp':i/10,'frame_number':i,'angles':{'knee_angle':120}} for i,k in enumerate(phases if phases is not None else insights.PHASES)])
        with metrics.database() as db:
            db.execute('UPDATE reports SET created=? WHERE id=?',(self.now+created,task))
            db.execute('UPDATE ops_quality SET finished=? WHERE task=?',(self.now+created+5,task))
    def record(self, action, at, visitor='v', user=None, task=None, details=None):
        insights.record(action,visitor,user,task,details,self.now+at)
    def admin(self):
        app.dependency_overrides[get_current_user_required]=lambda:{'id':'admin','role':'admin','is_local':True}
    async def test_full_ordered_cohort_and_registration_branch(self):
        self.record('visit',0,details={'source':'reddit','landing':'/guides/shooting-form','campaign':'post18'})
        self.record('file_selected',1)
        self.report();self.record('result_viewed',20,task='first')
        self.record('result_viewed',21,task='first')
        self.record('registration_submitted',22)
        self.record('registered',25,user='u')
        trial_store.claim('v','u');self.record('claimed',30,user='u',task='first')
        self.report('again',None,'u',40);self.record('comparison_viewed',50,user='u',task='again')
        d=insights.overview(7)
        self.assertEqual([x['count'] for x in d['journey']],[1]*7)
        self.assertEqual(d['registered_after_view'],1)
        self.assertEqual(d['registration_submitted'],1)
        self.assertEqual(d['comparison_accounts'],1)
        self.assertEqual(d['landings'][0]['name'],'/guides/shooting-form')
        self.assertEqual(d['campaigns'][0]['counts'],[1]*7)
        self.assertEqual(d['quality_measured'],2)
        self.assertEqual(d['anomaly_count'],0)
    async def test_out_of_order_views_do_not_convert_and_old_account_not_new(self):
        self.record('registered',-5,user='old')
        self.record('visit',0);self.record('file_selected',1);self.report()
        self.record('result_viewed',5,task='first') # before completed
        trial_store.claim('v','old');self.record('claimed',30,user='old',task='first')
        d=insights.overview(7)
        self.assertEqual([x['count'] for x in d['journey']],[1,1,1,1,0,0,0])
        self.assertEqual(d['registered_after_view'],0)
    async def test_missing_phases_not_inferred_from_count_and_unknown_history(self):
        self.report(phases=['release_frame'])
        d=insights.task_detail('first')
        self.assertEqual(len(d['missing_phases']),7)
        self.assertNotIn('release_frame',[x['phase'] for x in d['missing_phases']])
        self.assertEqual(insights.overview(7)['anomaly_count'],1)
        self.assertNotIn('ip',d)
        with metrics.database() as db:db.execute('DELETE FROM ops_task_details')
        self.assertIsNone(insights.task_detail('first')['missing_phases'])
        self.assertEqual(insights.overview(7)['quality_measured'],0)
    async def test_private_details_media_and_expired_reports(self):
        self.report()
        path=settings.results_dir/'first';path.mkdir(parents=True)
        (path/'image.png').write_bytes(b'fake-test-image')
        (path/'result.json').write_text(json.dumps({'key_frames':[{'phase':'release_frame','image_url':'/results/first/image.png'}]}))
        for url in ['/api/v1/admin/analyses/first/detail','/api/v1/admin/analyses/first/media/0','/api/v1/admin/users/u/detail']:
            self.assertIn((await self.client.get(url)).status_code,(401,403))
        self.admin()
        self.assertEqual((await self.client.get('/api/v1/admin/analyses/first/detail')).status_code,200)
        self.assertEqual((await self.client.get('/api/v1/admin/analyses/first/media/0')).content,b'fake-test-image')
        self.assertEqual((await self.client.get('/api/v1/admin/analyses/first/media/-1')).status_code,404)
        with metrics.database() as db:db.execute('UPDATE reports SET expires=?',(time.time()-1,))
        self.assertEqual((await self.client.get('/api/v1/admin/analyses/first/media/0')).status_code,404)
    async def test_user_timeline_merges_local_feedback_and_retest(self):
        self.record('visit',0,details={'source':'reddit','landing':'/app'})
        self.report();trial_store.claim('v','u');insights.link('v',{'id':'u','created_at':self.now+25})
        with metrics.database() as db:
            db.execute('INSERT INTO ops_feedback VALUES (?,?,?,?)',('first',1,0,self.now+40))
            db.execute('INSERT INTO credit_changes VALUES (?,?,?,?,?,?)',(self.now+50,'admin','u',1,3,'Support'))
        with feedback_store.transaction() as db:
            db.execute('INSERT INTO records VALUES (?,?)',('retest',json.dumps({'id':'retest','owner':'supabase:u','state':'waiting','created_at':self.now+60,'parent':{'id':'first','version':1},'versions':[]})))
        self.admin();r=await self.client.get('/api/v1/admin/users/u/detail')
        self.assertEqual(r.status_code,200);d=r.json()
        actions={x['action'] for x in d['timeline']}
        self.assertTrue({'visit','registered','analysis','quality_feedback','credit_adjusted','retest'} <= actions)
        self.assertIn('cloud',d['errors'])
        other=(await self.client.get('/api/v1/admin/users/other/detail')).json()
        self.assertEqual(other['timeline'],[])
    async def test_clients_cannot_forge_registration_or_view_other_reports(self):
        await self.client.get('/api/v1/trial/status')
        self.report(visitor='other')
        self.assertEqual((await self.client.post('/api/v1/audit/journey',json={'action':'registered'})).status_code,422)
        self.assertEqual((await self.client.post('/api/v1/audit/journey',json={'action':'result_viewed','task':'first'})).status_code,404)
        self.assertEqual((await self.client.post('/api/v1/audit/visit',json={'landing':'/app?token=secret'})).status_code,422)
        self.assertEqual(insights.overview(7)['journey'][4]['count'],0)
