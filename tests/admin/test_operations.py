import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from app.services import admin_metrics as metrics
from app.services.trial_service import trial_store
from app.api.routes.admin import require_admin

class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.object(trial_store,'path',Path(self.temp.name)/'trial.sqlite3');self.patch.start()
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()
    def test_cohort_claim_is_not_double_counted(self):
        metrics.event('visitor','visit','reddit');metrics.event('visitor','visit','reddit')
        trial_store.reserve('one','visitor',None,'<video>.mov','hashed')
        metrics.quality('one',frames=5);trial_store.finish('one',True)
        trial_store.claim('visitor','user')
        d=metrics.snapshot(7)
        self.assertEqual([s['count'] for s in d['funnel']],[1,1,1,1])
        self.assertEqual(d['total'],1);self.assertEqual(d['saved_trials'],1)
        self.assertEqual(d['channels'][0]['source'],'reddit')
    def test_account_and_failed_trial_in_quality(self):
        trial_store.reserve('one',None,'user','one.mov','hash')
        trial_store.finish('one',True)
        trial_store.reserve('two','visitor',None,'two.mov','hash')
        metrics.quality('two',error='No pose');trial_store.finish('two',False)
        d=metrics.snapshot(7)
        self.assertEqual(d['failed'],1);self.assertEqual(d['completed'],1)
        self.assertIsNone(d['average_seconds'])
        self.assertEqual(d['recent'][0]['error'],'No pose')
        self.assertEqual(d['funnel'][1]['count'],0)
    def test_visit_after_analysis_does_not_enter_cohort(self):
        trial_store.reserve('one','visitor',None,'one.mov','hash')
        metrics.event('visitor','visit')
        self.assertEqual(metrics.snapshot(7)['funnel'][1]['count'],0)
    def test_requires_local_admin(self):
        for user in ({'role':'user'}, {'role':'admin','is_local':False}):
            with self.assertRaises(HTTPException):require_admin(user)
        self.assertEqual(require_admin({'role':'admin','is_local':True})['role'],'admin')

class OperationsHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import httpx
        from app.main import app
        self.app=app
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.object(trial_store,'path',Path(self.temp.name)/'trial.db');self.patch.start()
        self.client=httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://test')
    async def asyncTearDown(self):
        await self.client.aclose();self.app.dependency_overrides.clear();self.patch.stop();self.temp.cleanup()
    async def test_private_operations_and_visit_quota(self):
        from app.api.deps import get_current_user_required
        response=await self.client.get('/api/v1/admin/operations')
        self.assertIn(response.status_code,(401,403))
        self.app.dependency_overrides[get_current_user_required]=lambda:{'id':'member','role':'user'}
        self.assertEqual((await self.client.get('/api/v1/admin/operations')).status_code,403)
        await self.client.get('/api/v1/trial/status')
        self.assertEqual((await self.client.post('/api/v1/audit/visit',json={'source':'reddit'})).status_code,200)
        vid=self.client.cookies['shot_visitor'].split('.')[0]
        self.assertEqual(trial_store.remaining(vid),1)
        self.app.dependency_overrides[get_current_user_required]=lambda:{'id':'admin','role':'admin','is_local':True}
        response=await self.client.get('/api/v1/admin/operations')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['funnel'][0]['count'],1)
        self.assertEqual((await self.client.get('/api/v1/admin/operations?days=999')).status_code,422)
        self.assertEqual((await self.client.post('/api/v1/audit/visit',json={'source':'x'*81})).status_code,422)
    async def test_credit_reason_and_failure_are_not_success(self):
        from unittest.mock import AsyncMock
        from app.api.deps import get_current_user_required
        from app.api.routes.admin import db_service
        self.app.dependency_overrides[get_current_user_required]=lambda:{'id':'admin','role':'admin','is_local':True}
        with patch.object(db_service,'is_available',return_value=True), patch.object(db_service,'get_user_credits',new=AsyncMock(return_value=3)), patch.object(db_service,'increment_user_credits',new=AsyncMock(return_value=5)):
            path='/api/v1/admin/users/member/credits'
            self.assertEqual((await self.client.put(path,json={'amount':2})).status_code,400)
            self.assertEqual((await self.client.put(path,json={'amount':2,'reason':'Support compensation'})).status_code,200)
            change=metrics.snapshot(7)['credit_changes'][0]
            self.assertEqual((change['before_balance'],change['after_balance'],change['actor']),(3,5,'admin'))
        with patch.object(db_service,'is_available',return_value=True), patch.object(db_service,'get_user_credits',new=AsyncMock(return_value=3)), patch.object(db_service,'increment_user_credits',new=AsyncMock(return_value=-1)):
            self.assertEqual((await self.client.put(path,json={'amount':2,'reason':'Retry'})).status_code,503)
        self.assertEqual(len(metrics.snapshot(7)['credit_changes']),1)
    async def test_report_feedback_is_private_and_idempotent(self):
        from app.api.deps import get_current_user_optional
        self.app.dependency_overrides[get_current_user_optional]=lambda:None
        await self.client.get('/api/v1/trial/status')
        await self.client.post('/api/v1/audit/visit',json={})
        vid=self.client.cookies['shot_visitor'].split('.')[0]
        trial_store.reserve('report',vid,None,'shot.mov','hash');trial_store.finish('report',True)
        path='/api/v1/trial/reports/report/feedback'
        self.assertEqual((await self.client.post(path,json={'helpful':True,'accurate':False})).status_code,200)
        self.assertEqual((await self.client.post(path,json={'helpful':False,'accurate':True})).status_code,200)
        self.assertEqual(metrics.snapshot(7)['feedback'],{'responses':1,'helpful':0,'accurate':1})
        self.client.cookies.clear()
        self.assertEqual((await self.client.post(path,json={'helpful':True,'accurate':True})).status_code,401)
        self.assertEqual(metrics.snapshot(7)['feedback']['responses'],1)
