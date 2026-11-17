"""Opt-in local-only end-to-end QA. Creates clearly labelled local demo records."""
import json
import sys
import time
from pathlib import Path
import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import settings

base='http://127.0.0.1:8000'
video=settings.base_dir/'modelVideo'/'reddit1009.mov'
with httpx.Client(base_url=base, timeout=90) as c:
    login=c.post('/api/v1/auth/local-login',json={'username':'admin','password':settings.local_admin_password})
    login.raise_for_status()
    c.headers['Authorization']='Bearer '+login.json()['token']
    with video.open('rb') as f:
        response=c.post('/api/v1/videos/upload?retain_for_feedback=true',files={'file':('Local QA - first.mov',f,'video/quicktime')})
    response.raise_for_status();task=response.json()['task_id']
    for _ in range(90):
        r=c.get('/api/v1/feedback/tasks/'+task);r.raise_for_status()
        if r.json()['analysis_state'] in ('completed','failed'):break
        time.sleep(1)
    assert r.json()['analysis_state'] == 'completed', 'Initial analysis failed or timed out'
    print('Initial automatic analysis:',r.json()['analysis_state'],flush=True)
    path='/api/v1/feedback/tasks/'+task
    r=c.post(path+'/request',json={'goal':'consistency','context':'stationary','problem':'LOCAL QA DEMO — test the feedback and follow-up workflow; not a technical assessment.'});r.raise_for_status()
    draft=dict(revision=0,observation='Demo only: this annotation marks a moment for review, not a diagnosis.',focus='Demo: review one change at a time',drill='Demo workflow: choose a practice with your reviewer, then record what you noticed.',retest='For this demo, upload a short clip from the same angle.',criteria='Check whether the instructions and comparison are understandable.',evidence_seconds=.6,author='Local QA — demo, not coaching advice',frames=[])
    r=c.put(path+'/draft',json=draft);r.raise_for_status()
    r=c.post(path+'/publish',json={'revision':1});r.raise_for_status()
    r=c.post(path+'/shares');r.raise_for_status();link=r.json()['url']
    share=c.post('/api/v1/feedback/shared',json={'token':link.split('#')[1]});share.raise_for_status()
    media=c.get(share.json()['video'],headers={'Range':'bytes=0-99'});assert media.status_code==206
    c.delete(path+'/shares').raise_for_status()
    assert c.get(share.json()['video']).status_code==404
    practice={'completion':'partial','feeling':'unsure','notes':'LOCAL QA: reusing the source clip to test comparison, not evidence of improvement.','attempts':10,'makes':5}
    with video.open('rb') as f:
        r=c.post(path+'/followup',data={'practice':json.dumps(practice),'version':'1','key':'local-qa-'+task},files={'file':('Local QA - follow-up.mov',f,'video/quicktime')})
    r.raise_for_status();child=r.json()['id']
    for _ in range(90):
        r=c.get('/api/v1/feedback/tasks/'+child);r.raise_for_status()
        if r.json()['analysis_state'] in ('completed','failed'):break
        time.sleep(1)
    assert r.json()['analysis_state'] == 'completed', 'Follow-up analysis failed or timed out'
    assert r.json()['previous']['review']['version']==1
    assert len(r.json()['timeline'])==2
    print('Follow-up automatic analysis:',r.json()['analysis_state'],flush=True)
    out={'first':task,'followup':child,'first_analysis':c.get(path).json()['analysis_state'],'followup_analysis':r.json()['analysis_state'],'share_revocation':'passed','comparison':'passed'}
    dest=settings.base_dir/'artifacts'/'feedback-qa';dest.mkdir(parents=True,exist_ok=True)
    (dest/'smoke-result.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out),flush=True)
