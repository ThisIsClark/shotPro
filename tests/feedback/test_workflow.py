"""Isolated pilot integration tests: no production DB, credits, or user files."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import httpx
import numpy as np
from fastapi import FastAPI, Header

from app.api.routes import feedback as api
from app.api.deps import get_current_user_required
from app.services.feedback_service import FeedbackStore


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = FeedbackStore(self.root / 'private')
        self.patch = patch.object(api, 'store', self.store)
        self.patch.start()
        self.app = FastAPI()
        self.app.include_router(api.router, prefix='/api/v1')
        async def user(x_test_user: str = Header('player')):
            return {'id': x_test_user, 'is_local': True, 'role': 'admin' if x_test_user == 'admin' else 'user'}
        self.app.dependency_overrides[get_current_user_required] = user
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test')
        self.video = self.root / 'clip.mp4'
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*'mp4v'), 30, (64, 64))
        for i in range(30):
            writer.write(np.full((64, 64, 3), i * 5, dtype=np.uint8))
        writer.release()
        self.store.capture('first', {'id':'player','is_local':True}, self.video, 'clip.mp4', 1)
        self.base='/api/v1/feedback'

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patch.stop()
        self.temp.cleanup()

    async def request_feedback(self):
        self.store.grant('local:player',1)
        r=await self.client.post(self.base+'/tasks/first/request',json={'goal':'consistency','context':'stationary','problem':'Shot feels inconsistent'})
        self.assertEqual(r.status_code,200,r.text)

    async def publish(self):
        await self.request_feedback()
        body=dict(revision=0,observation='A pause is visible.',focus='Keep the motion connected.',drill='Practice ten easy shots, watching the transition.',retest='Film from the same side.',criteria='Check the pause.',evidence_seconds=.3,author='Test reviewer (demo)',frames=[])
        r=await self.client.put(self.base+'/tasks/first/draft',headers={'X-Test-User':'admin'},json=body)
        self.assertEqual(r.status_code,200,r.text)
        r=await self.client.post(self.base+'/tasks/first/publish',headers={'X-Test-User':'admin'},json={'revision':1})
        self.assertEqual(r.status_code,200,r.text)
        return body

    async def test_invitation_ownership_and_persistence(self):
        body={'goal':'consistency','context':'stationary','problem':'Test'}
        r=await self.client.post(self.base+'/tasks/first/request',json=body)
        self.assertEqual(r.status_code,403)
        await self.request_feedback()
        r=await self.client.get(self.base+'/tasks/first',headers={'X-Test-User':'other'})
        self.assertEqual(r.status_code,404)
        r=await self.client.post(self.base+'/tasks/first/request',json=body)
        self.assertEqual(r.status_code,200) # idempotent, no second charge
        self.assertEqual(FeedbackStore(self.store.root).get('first')['state'],'waiting')
        r=await self.client.put(self.base+'/tasks/first/draft',json={'revision':0})
        self.assertEqual(r.status_code,403)

    async def test_publish_validation_revision_and_snapshot(self):
        await self.request_feedback()
        r=await self.client.post(self.base+'/tasks/first/publish',headers={'X-Test-User':'admin'},json={'revision':0})
        self.assertEqual(r.status_code,422)
        body=await self.publish()
        r=await self.client.put(self.base+'/tasks/first/draft',headers={'X-Test-User':'admin'},json=body)
        self.assertEqual(r.status_code,409)
        body.update(revision=1,focus='UNPUBLISHED PRIVATE TEXT')
        r=await self.client.put(self.base+'/tasks/first/draft',headers={'X-Test-User':'admin'},json=body)
        self.assertEqual(r.status_code,200)
        r=await self.client.get(self.base+'/tasks/first')
        self.assertNotIn('UNPUBLISHED',r.text)
        self.assertNotIn('draft',r.json())
        self.assertEqual(r.json()['review']['version'],1)

    async def test_sharing_range_and_revocation(self):
        await self.publish()
        share=await self.client.post(self.base+'/tasks/first/shares')
        token=share.json()['url'].split('#')[1]
        r=await self.client.post(self.base+'/shared',json={'token':token})
        self.assertEqual(r.status_code,200)
        self.assertNotIn('owner',r.json())
        r=await self.client.get('/api/v1/feedback/shared-media/first/original.mp4',headers={'Range':'bytes=0-99'})
        self.assertEqual(r.status_code,206)
        self.assertEqual(len(r.content),100)
        await self.client.delete(self.base+'/tasks/first/shares')
        r=await self.client.get('/api/v1/feedback/shared-media/first/original.mp4')
        self.assertEqual(r.status_code,404)
        r=await self.client.post(self.base+'/shared',json={'token':token})
        self.assertEqual(r.status_code,404)

    async def test_private_media_and_cookie_scope(self):
        r=await self.client.get(self.base+'/media/first/original.mp4')
        self.assertEqual(r.status_code,401)
        await self.client.post(self.base+'/media-session')
        r=await self.client.get(self.base+'/media/first/original.mp4',headers={'Range':'bytes=-50'})
        self.assertEqual(r.status_code,206)
        self.assertEqual(len(r.content),50)
        r=await self.client.get(self.base+'/media/first/original.mp4',headers={'Range':'bytes=99999999-'})
        self.assertEqual(r.status_code,416)
        await self.client.post(self.base+'/media-session',headers={'X-Test-User':'other'})
        r=await self.client.get(self.base+'/media/first/original.mp4')
        self.assertEqual(r.status_code,404)

    async def test_followup_validation_idempotence_and_comparison(self):
        await self.publish()
        import json
        practice={'completion':'done','feeling':'smoother','attempts':10,'makes':6}
        data={'practice':json.dumps(practice),'version':'1','key':'stable-key-123'}
        files={'file':('clip.mp4',self.video.read_bytes(),'video/mp4')}
        with patch.object(api,'run_followup',lambda task_id:None):
            r=await self.client.post(self.base+'/tasks/first/followup',data=data,files=files)
            self.assertEqual(r.status_code,200,r.text)
            child=r.json()['id']
            again=await self.client.post(self.base+'/tasks/first/followup',data=data,files=files)
            self.assertEqual(again.json()['id'],child)
        r=await self.client.get(self.base+'/tasks/'+child)
        self.assertEqual(r.json()['previous']['review']['version'],1)
        self.assertEqual(r.json()['practice']['makes'],6)
        self.assertEqual(len(r.json()['timeline']),2)
        versions = self.store.get('first')['versions']
        self.store.change(child, lambda r:r.update(versions=versions))
        third=await self.client.post(self.base+'/tasks/'+child+'/followup',data=data,files=files)
        self.assertEqual(third.status_code,403)
        data['key']='different-key'
        r=await self.client.post(self.base+'/tasks/first/followup',data=data,files=files)
        self.assertEqual(r.status_code,409)
        practice['makes']=11
        data['practice']=json.dumps(practice)
        r=await self.client.post(self.base+'/tasks/first/followup',data=data,files=files)
        self.assertEqual(r.status_code,422)

    async def test_manual_frame_and_delete(self):
        await self.publish()
        r=await self.client.post(self.base+'/tasks/first/frame',headers={'X-Test-User':'admin'},json={'seconds':.3})
        self.assertEqual(r.status_code,200,r.text)
        self.assertTrue((self.store.root/'first'/r.json()['asset']).exists())
        r=await self.client.post(self.base+'/tasks/first/frame',headers={'X-Test-User':'admin'},json={'seconds':2})
        self.assertEqual(r.status_code,422)
        r=await self.client.delete(self.base+'/tasks/first')
        self.assertEqual(r.status_code,200)
        self.assertFalse((self.store.root/'first').exists())
        r=await self.client.get(self.base+'/tasks/first')
        self.assertEqual(r.status_code,404)

    async def test_interrupted_analysis_recovery(self):
        self.store.change('first',lambda r:r.update(analysis_state='processing'))
        FeedbackStore(self.store.root).recover()
        self.assertEqual(self.store.get('first')['analysis_state'],'failed')
        self.assertTrue((self.store.root/'first'/'original.mp4').exists())

    async def test_share_keeps_original_published_version(self):
        body = await self.publish()
        shared = await self.client.post(self.base+'/tasks/first/shares')
        token = shared.json()['url'].split('#')[1]
        body.update(revision=1, focus='A different published focus')
        await self.client.put(self.base+'/tasks/first/draft', headers={'X-Test-User':'admin'}, json=body)
        r = await self.client.post(self.base+'/tasks/first/publish', headers={'X-Test-User':'admin'}, json={'revision':2})
        self.assertEqual(r.json()['review']['version'], 2)
        r = await self.client.post(self.base+'/shared', json={'token':token})
        self.assertEqual(r.json()['review']['version'], 1)
        self.assertNotIn('author_subject', r.json()['review'])

    async def test_media_logout_revokes_cookie(self):
        await self.client.post(self.base+'/media-session')
        self.assertEqual((await self.client.get(self.base+'/media/first/original.mp4')).status_code, 200)
        await self.client.delete(self.base+'/media-session')
        self.assertEqual((await self.client.get(self.base+'/media/first/original.mp4')).status_code, 401)

    async def test_interrupted_upload_reservation_can_retry(self):
        self.store.change('first', lambda r:r.update(followup={'id':'reserved','key':'stable-key'}))
        orphan = self.store.root/'reserved'
        orphan.mkdir()
        (orphan/'original.mov').write_bytes(b'incomplete')
        self.store.recover()
        self.assertFalse(orphan.exists())
        self.assertEqual(self.store.get('first')['followup']['key'],'stable-key')

    async def test_retry_is_claimed_once(self):
        self.store.change('first', lambda r:r.update(analysis_state='failed'))
        with patch.object(api,'run_followup',lambda task_id:None):
            first = await self.client.post(self.base+'/tasks/first/retry', headers={'X-Test-User':'admin'})
            second = await self.client.post(self.base+'/tasks/first/retry', headers={'X-Test-User':'admin'})
        self.assertEqual(first.status_code,200)
        self.assertEqual(second.status_code,409)

    async def test_private_media_survives_legacy_ten_task_cleanup(self):
        from app.main import cleanup_disk_tasks
        from app.config import settings
        import json
        results = self.root/'legacy-results'
        uploads = self.root/'legacy-uploads'
        results.mkdir(); uploads.mkdir()
        for i in range(12):
            folder=results/str(i);folder.mkdir()
            (folder/'result.json').write_text(json.dumps({'created_at':f'2026-01-{i+1:02d}'}))
        with patch.object(settings,'results_dir',results), patch.object(settings,'upload_dir',uploads):
            cleanup_disk_tasks()
        self.assertEqual(len(list(results.iterdir())),10)
        self.assertTrue((self.store.root/'first'/'original.mp4').is_file())
        self.assertIsNotNone(self.store.get('first'))

if __name__=='__main__':
    unittest.main()
