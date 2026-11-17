"""Isolated quota, ownership and HTTP flow regression; no real accounts or paid credits."""
import asyncio
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi import HTTPException
from app.main import app
from app.api.routes import upload
from app.api.deps import get_current_user_optional, get_current_user_required
from app.config import settings
from app.services.trial_service import trial_store


class TrialTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(trial_store, 'path', self.root/'trial.db'),
                        patch.object(settings, 'results_dir', self.root/'results'),
                        patch.object(settings, 'upload_dir', self.root/'uploads'),
                        patch.object(upload.db_service, 'is_available', return_value=False)]
        for p in self.patches: p.start()
        settings.results_dir.mkdir(); settings.upload_dir.mkdir()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://test')
        self.other = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://test')
        self.media_app = next(r.app for r in app.routes if getattr(r, 'path', '') == '/results')
        self.patches.append(patch.object(self.media_app, 'all_directories', [str(settings.results_dir)]))
        self.patches[-1].start()
        self.user = None
        app.dependency_overrides[get_current_user_optional] = lambda: self.user
        async def required():
            if not self.user: raise HTTPException(401, 'Login required')
            return self.user
        app.dependency_overrides[get_current_user_required] = required

    async def asyncTearDown(self):
        await self.client.aclose(); await self.other.aclose()
        app.dependency_overrides.clear()
        upload.task_store.clear()
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    async def visitor(self, client=None):
        c = client or self.client
        r = await c.get('/api/v1/trial/status')
        self.assertEqual(r.status_code, 200)
        return c.cookies['shot_visitor'].split('.')[0]

    def report(self, task, vid, owner=None):
        trial_store.reserve(task, vid, owner, 'shot.mp4', 'test-ip')
        folder = settings.results_dir/task; folder.mkdir()
        (folder/'result.json').write_text(json.dumps({'key_frames': [{'phase':'release_frame', 'angles':{'knee_angle':160}}]}))
        trial_store.finish(task, True)

    async def test_refresh_restart_and_concurrent_reservation(self):
        vid = await self.visitor()
        self.assertEqual(vid, await self.visitor())
        def reserve(i):
            try: trial_store.reserve(str(i), vid, None, 'shot', 'ip'); return True
            except HTTPException: return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(reserve, range(4)))
        self.assertEqual(sum(outcomes), 1)
        winner = str(outcomes.index(True))
        self.assertEqual((await self.client.get('/api/v1/trial/status')).json()['credits_remaining'], 0)
        trial_store.finish(winner, False)
        self.assertEqual(trial_store.remaining(vid), 1)
        self.report('finished', vid)
        from app.services.trial_service import TrialStore
        self.assertEqual(TrialStore(trial_store.path).remaining(vid), 0)

    async def test_claim_is_idempotent_private_and_does_not_grant_extra_credits(self):
        vid = await self.visitor(); self.report('report-a', vid)
        self.assertEqual((await self.other.get('/api/v1/videos/tasks/report-a/result')).status_code, 401)
        await self.visitor(self.other)
        self.assertEqual((await self.other.get('/api/v1/videos/tasks/report-a/result')).status_code, 404)
        self.assertEqual((await self.client.get('/api/v1/videos/tasks/report-a/result')).status_code, 200)
        self.assertEqual((await self.client.get('/api/v1/videos/history')).status_code, 401)
        self.user = {'id':'alice'}
        self.assertEqual((await self.client.post('/api/v1/trial/claim')).json()['claimed'], ['report-a'])
        self.assertEqual((await self.client.post('/api/v1/trial/claim')).json()['claimed'], [])
        self.assertEqual(len((await self.client.get('/api/v1/videos/history')).json()), 1)
        self.assertIsNone(trial_store.get('report-a')['expires'])
        self.user = {'id':'bob'}
        self.assertEqual((await self.client.get('/api/v1/videos/history')).json(), [])
        self.assertEqual((await self.client.get('/api/v1/videos/tasks/report-a/result')).status_code, 404)
        self.assertEqual((await self.client.delete('/api/v1/videos/tasks/report-a')).status_code, 404)
        self.user = None
        self.assertEqual((await self.client.get('/api/v1/videos/tasks/report-a/result')).status_code, 404)
        self.assertEqual(trial_store.remaining(vid), 0)

    async def test_expiry_and_retention(self):
        vid = await self.visitor(); self.report('expired', vid)
        self.report('saved', None, 'alice')
        with trial_store.db() as db: db.execute('UPDATE reports SET expires=1 WHERE id=?', ('expired',))
        self.assertEqual((await self.client.get('/api/v1/videos/tasks/expired/result')).status_code, 404)
        trial_store.maintenance()
        self.assertFalse((settings.results_dir/'expired').exists())
        self.assertTrue((settings.results_dir/'saved/result.json').exists())
        from app.main import cleanup_disk_tasks
        cleanup_disk_tasks()
        self.assertTrue((settings.results_dir/'saved/result.json').exists())

    async def test_limits_and_tampered_cookie(self):
        vid = await self.visitor()
        with patch.object(settings, 'trial_daily_limit', 0):
            with self.assertRaises(HTTPException) as ctx: trial_store.reserve('x', vid, None, 'x', 'ip')
            self.assertEqual(ctx.exception.status_code, 429)
        self.client.cookies.set('shot_visitor', vid+'.fake', domain='test.local', path='/')
        # A forged signed identity cannot retrieve an existing private report.
        self.report('secret', vid)
        self.client.cookies.clear()
        self.client.cookies.set('shot_visitor', vid+'.fake')
        self.assertEqual((await self.client.get('/api/v1/videos/tasks/secret/result')).status_code, 401)

    async def test_real_upload_validation_and_failed_analysis_releases_trial(self):
        import cv2
        import numpy as np
        video = self.root/'tiny.mp4'
        writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'mp4v'), 10, (64,64))
        for _ in range(5): writer.write(np.zeros((64,64,3), dtype=np.uint8))
        writer.release()
        vid = await self.visitor()
        # Exercise real upload and failure handling, without running MediaPipe.
        with patch.object(upload, 'AnalysisService', side_effect=RuntimeError('no pose')):
            r = await self.client.post('/api/v1/videos/upload', files={'file':('tiny.mp4', video.read_bytes(), 'video/mp4')})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(trial_store.get(r.json()['task_id'])['state'], 'failed')
        self.assertEqual(trial_store.remaining(vid), 1)
        r = await self.client.post('/api/v1/videos/upload', files={'file':('broken.mp4', b'bad', 'video/mp4')})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(trial_store.remaining(vid), 1)

    async def test_static_media_uses_signed_session_and_logout_revokes_browser_access(self):
        vid = await self.visitor(); self.report('media', vid)
        url = '/results/media/result.json'
        self.assertEqual((await self.client.get(url)).status_code, 200)
        self.assertNotEqual((await self.other.get(url)).status_code, 200)
        self.user = {'id': 'alice'}
        await self.client.post('/api/v1/trial/claim')
        self.assertEqual((await self.client.get(url)).status_code, 200)
        self.user = None
        await self.client.post('/api/v1/trial/logout')
        self.assertEqual((await self.client.get(url)).status_code, 404)
        self.assertNotEqual((await self.other.get('/api/v1/export/media/pdf')).status_code, 200)

    async def test_cross_device_authenticated_history_and_delete(self):
        self.report('owned', None, 'alice')
        self.user = {'id': 'alice'}
        self.assertEqual(len((await self.other.get('/api/v1/videos/history')).json()), 1)
        self.assertEqual((await self.other.get('/api/v1/videos/tasks/owned/status')).json()['status'], 'completed')
        self.assertEqual((await self.other.delete('/api/v1/videos/tasks/owned')).status_code, 200)
        self.assertEqual((await self.other.get('/api/v1/videos/history')).json(), [])
        self.assertEqual((await self.other.get('/api/v1/videos/tasks/owned/result')).status_code, 404)

    async def test_abandoned_job_status_does_not_poll_forever(self):
        vid = await self.visitor()
        trial_store.reserve('abandoned', vid, None, 'clip', 'ip')
        upload.task_store['abandoned'] = {'status':'processing', 'progress':25, 'message':'Analyzing'}
        with trial_store.db() as db:
            db.execute('UPDATE reports SET created=1 WHERE id=?', ('abandoned',))
        trial_store.maintenance()
        response = await self.client.get('/api/v1/videos/tasks/abandoned/status')
        self.assertEqual(response.json()['status'], 'failed')
        self.assertEqual(trial_store.remaining(vid), 1)

    async def test_late_completion_cannot_revive_deleted_or_abandoned_report(self):
        vid = await self.visitor()
        trial_store.reserve('late', vid, None, 'clip', 'ip')
        trial_store.delete('late')
        trial_store.finish('late', True)
        self.assertEqual(trial_store.get('late')['state'], 'deleted')
        trial_store.reserve('stale', vid, None, 'clip', 'ip')
        with trial_store.db() as db: db.execute('UPDATE reports SET created=1 WHERE id=?', ('stale',))
        trial_store.maintenance()
        trial_store.finish('stale', True)
        self.assertEqual(trial_store.get('stale')['state'], 'failed')

    async def test_claim_while_processing_and_no_cross_account_reclaim(self):
        vid = await self.visitor()
        trial_store.reserve('processing', vid, None, 'clip', 'ip')
        self.user = {'id':'alice'}
        self.assertEqual((await self.client.post('/api/v1/trial/claim')).json()['claimed'], ['processing'])
        self.user = {'id':'bob'}
        self.assertEqual((await self.client.post('/api/v1/trial/claim')).json()['claimed'], [])
        trial_store.finish('processing', True)
        self.assertEqual(trial_store.get('processing')['owner'], 'alice')
        self.assertEqual(trial_store.remaining(vid), 0)

    async def test_ip_limit_failed_attempts_and_cookie_flags(self):
        response = await self.client.get('/api/v1/trial/status')
        cookie = response.headers['set-cookie'].lower()
        for flag in ('httponly','secure','samesite=lax','max-age=31536000'): self.assertIn(flag, cookie)
        with patch.object(settings,'trial_ip_hourly_limit',1):
            trial_store.reserve('first','visitor-1',None,'clip','shared-ip')
            trial_store.finish('first',False)
            with self.assertRaises(HTTPException) as ctx:
                trial_store.reserve('second','visitor-2',None,'clip','shared-ip')
            self.assertEqual(ctx.exception.status_code,429)
            trial_store.reserve('elsewhere','visitor-3',None,'clip','other-ip')

    async def test_delete_does_not_refund_successful_trial(self):
        vid = await self.visitor(); self.report('used',vid)
        self.assertEqual((await self.client.delete('/api/v1/videos/tasks/used')).status_code,200)
        self.assertEqual(trial_store.remaining(vid),0)

    async def test_real_bearer_auth_and_media_cookie(self):
        from app.services.jwt_service import jwt_service
        app.dependency_overrides.clear()
        self.report('jwt-report',None,'alice')
        token = jwt_service.create_token({'id':'alice','is_local':True})
        headers={'Authorization':'Bearer '+token}
        self.assertEqual((await self.client.get('/api/v1/videos/history',headers=headers)).status_code,200)
        self.assertEqual((await self.client.get('/api/v1/videos/tasks/jwt-report/result',headers=headers)).status_code,200)
        self.assertEqual((await self.client.post('/api/v1/trial/claim',headers=headers)).status_code,200)
        self.assertEqual((await self.client.get('/results/jwt-report/result.json')).status_code,200)
        wrong = jwt_service.create_token({'id':'bob','is_local':True})
        self.assertEqual((await self.other.get('/results/jwt-report/result.json',headers={'Authorization':'Bearer '+wrong})).status_code,404)
        self.assertEqual((await self.other.post('/api/v1/trial/claim',headers={'Authorization':'Bearer invalid'})).status_code,401)
