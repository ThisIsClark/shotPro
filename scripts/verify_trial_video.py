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
        rhythm = result['shot_rhythm']
        assert status['result']['shot_rhythm']['style'] == rhythm['style']
        if rhythm['style'] != 'unclear':
            from PIL import Image
            poster_url = f'/api/v1/export/{task}/images/shot-rhythm.png'
            poster = await guest.get(poster_url)
            assert poster.status_code == 200 and poster.headers['content-type'] == 'image/png'
            assert 'attachment' in poster.headers['content-disposition']
            with Image.open(io.BytesIO(poster.content)) as image:
                assert image.format == 'PNG' and image.size == (1080, 1350)
                image.verify()
            assert (await account.get(poster_url)).status_code in (401, 404)
            replay = rhythm['replay_url']
            assert (await guest.get(replay)).status_code == 200
            assert (await account.get(replay)).status_code in (401,404)
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

async def verify_engine(video, origin):
    from unittest.mock import patch
    import httpx
    from app.main import app
    from app.config import settings
    from app.services import engine_identity
    from app.services.trial_service import trial_store
    from app.api.routes.upload import task_store

    # Substitute only the external identity provider. Exercise actual ASGI upload,
    # analysis, private media middleware, disk fallback and deletion.
    def engine(request):
        assert str(request.url) == origin + '/_auth/me'
        member = {'session=first': 'alice', 'session=second': 'bob',
                  'session=renewed': 'alice'}.get(request.headers.get('cookie'))
        payload = {'logged_in': bool(member), 'member': {'id': member}}
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url=origin) as client:
        factory = httpx.AsyncClient
        def verification_client(**kwargs):
            return factory(transport=httpx.MockTransport(engine), **kwargs)
        headers = {'origin': origin, 'cookie': 'session=first'}
        with patch.object(settings, 'engine_auth_origin', origin), patch.object(
                engine_identity.httpx, 'AsyncClient', side_effect=verification_client):
            unknown = await client.get('/api/v1/videos/history', headers={'cookie':'session=expired'})
            assert unknown.status_code == 401
            bad_origin = await client.post('/api/v1/videos/upload', headers={
                'cookie':'session=first','origin':'https://unrelated.example'})
            assert bad_origin.status_code == 403
            video_bytes = video.read_bytes()
            response = await client.post('/api/v1/videos/upload', headers=headers,
                                         files={'file':('practice.MP4', video_bytes, 'video/mp4')})
            assert response.status_code == 200, response.text
            task = response.json()['task_id']
            assert trial_store.get(task)['state'] == 'completed'
            owner = trial_store.get(task)['owner']
            assert owner == ('gefei-staging:alice' if 'staging.' in origin else 'gefei:formrefine.ai:alice')
            task_store.pop(task, None)
            prefix = f'/api/v1/videos/tasks/{task}'
            headers['cookie'] = 'session=renewed'
            assert task in [r['task_id'] for r in (await client.get('/api/v1/videos/history',headers=headers)).json()]
            assert (await client.get(prefix+'/source',headers=headers)).content == video_bytes
            result = (await client.get(prefix+'/result',headers=headers)).json()
            frame = result['key_frames'][0]['image_url']
            assert (await client.get(frame,headers=headers)).status_code == 200
            bob = {**headers,'cookie':'session=second'}
            private_urls = [prefix+'/source', prefix+'/result', frame, f'/api/v1/export/{task}/pdf']
            if result['shot_rhythm']['style'] != 'unclear':
                replay = result['shot_rhythm']['replay_url']
                assert (await client.get(replay, headers=headers)).status_code == 200
                private_urls.append(replay)
            for url in private_urls:
                assert (await client.get(url,headers=bob)).status_code == 404, url
            assert (await client.delete(prefix,headers=bob)).status_code == 404
            assert (await client.delete(prefix,headers=headers)).status_code == 200
            assert not list(settings.upload_dir.glob(task + '.*'))
            assert (await client.get(prefix+'/source',headers=headers)).status_code == 404
    print(f'PASS {origin} session ownership, source retention, cross-account isolation and deletion')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='trial-video-') as temp:
        os.environ.update(SUPABASE_URL='',SUPABASE_ANON_KEY='',SUPABASE_SERVICE_KEY='',CREEM_API_KEY='',
                          RESULTS_DIR=temp+'/results',UPLOAD_DIR=temp+'/uploads',FEEDBACK_DIR=temp+'/feedback',
                          TRIAL_DB_PATH=temp+'/trial.db',MPLCONFIGDIR=temp+'/matplotlib')
        asyncio.run(verify(args.video.resolve()))
        asyncio.run(verify_engine(args.video.resolve(), "https://staging.formrefine.ai"))
        asyncio.run(verify_engine(args.video.resolve(), "https://formrefine.ai"))
