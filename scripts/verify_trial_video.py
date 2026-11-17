#!/usr/bin/env python3
"""Real local video -> analysis -> export -> claim -> history -> delete, in temporary storage.
No real accounts, network database writes or payment calls. Run explicitly; requires MediaPipe.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import zipfile
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

async def verify(video):
    import httpx
    from app.main import app
    from app.services.jwt_service import jwt_service
    from app.services.trial_service import trial_store, TrialStore
    from app.config import settings
    def auth(who):
        return {'Authorization':'Bearer '+jwt_service.create_token({'id':who,'is_local':True})}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://local-test',timeout=180) as guest, httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://local-test') as account:
        assert (await guest.get('/api/v1/trial/status')).json()['credits_remaining']==1
        files={'file':(video.name,video.read_bytes(),'video/mp4')}
        r=await guest.post('/api/v1/videos/upload',files=files)
        assert r.status_code==200,r.text
        task=r.json()['task_id']
        status=(await guest.get(f'/api/v1/videos/tasks/{task}/status')).json()
        assert status['status']=='completed',status
        result=(await guest.get(f'/api/v1/videos/tasks/{task}/result')).json()
        assert len(result['key_frames'])>=4
        for frame in result['key_frames']:
            image=await guest.get(frame['image_url'])
            assert image.status_code==200
            assert (await account.get(frame['image_url'])).status_code in (401,404)
        assert (await guest.get('/api/v1/trial/status')).json()['credits_remaining']==0
        assert (await guest.post('/api/v1/videos/upload',files=files)).status_code==403
        export=await guest.get(f'/api/v1/export/{task}/images/keyframes')
        assert export.status_code==200,export.text[:200]
        with zipfile.ZipFile(io.BytesIO(export.content)) as archive:
            assert len(archive.namelist())>=4
        pdf=await guest.get(f'/api/v1/export/{task}/pdf?language=en-US')
        assert pdf.status_code==200 and pdf.content.startswith(b'%PDF'),pdf.status_code
        claim=await guest.post('/api/v1/trial/claim',headers=auth('smoke-alice'))
        assert claim.json()['claimed']==[task],claim.text
        assert (await guest.post('/api/v1/trial/claim',headers=auth('smoke-alice'))).json()['claimed']==[]
        history=await account.get('/api/v1/videos/history',headers=auth('smoke-alice'))
        assert history.json()[0]['task_id']==task,history.text
        assert (await account.get(f'/api/v1/videos/tasks/{task}/result',headers=auth('smoke-bob'))).status_code==404
        assert (await account.delete(f'/api/v1/videos/tasks/{task}',headers=auth('smoke-bob'))).status_code==404
        assert (await account.get(f'/api/v1/videos/tasks/{task}/result',headers=auth('smoke-alice'))).status_code==200
        persisted=TrialStore(settings.trial_db_path).get(task)
        assert persisted['owner']=='smoke-alice' and persisted['expires'] is None
        assert (await account.delete(f'/api/v1/videos/tasks/{task}',headers=auth('smoke-alice'))).status_code==200
        assert (await account.get('/api/v1/videos/history',headers=auth('smoke-alice'))).json()==[]
        assert (await guest.get('/api/v1/trial/status')).json()['credits_remaining']==0
        print('PASS real-video lifecycle:',json.dumps({'video':video.name,'keyframes':len(result['key_frames']), 'zip':True,'pdf':True,'claim':True,'cross_account_isolation':True,'persistent_history':True,'delete':True}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='trial-video-') as temp:
        os.environ.update(SUPABASE_URL='',SUPABASE_ANON_KEY='',SUPABASE_SERVICE_KEY='',CREEM_API_KEY='',
                          RESULTS_DIR=temp+'/results',UPLOAD_DIR=temp+'/uploads',FEEDBACK_DIR=temp+'/feedback',
                          TRIAL_DB_PATH=temp+'/trial.db',MPLCONFIGDIR=temp+'/matplotlib')
        asyncio.run(verify(args.video.resolve()))
