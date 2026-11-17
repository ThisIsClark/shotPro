"""P0/P1 operational journeys. Facts are timestamped; missing history stays unknown."""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from fastapi import HTTPException
from .admin_metrics import database
from .trial_service import trial_store
from ..config import settings

PHASES = {
    'sync_frame_1': 'Dip point', 'sync_frame_2': 'Early lift',
    'max_hold_frame': 'Set point', 'release_frame': 'Release',
    'knee_min_frame': 'Deepest knee bend', 'elbow_min_frame': 'Elbow fold',
    'wrist_peak_frame': 'Wrist peak', 'follow_through_frame': 'Follow-through',
}

def init(db):
    db.execute('CREATE TABLE IF NOT EXISTS ops_journey (id INTEGER PRIMARY KEY, visitor TEXT, user_id TEXT, action TEXT, task TEXT, created REAL, details TEXT)')
    db.execute('CREATE INDEX IF NOT EXISTS journey_time ON ops_journey(created)')
    db.execute('CREATE INDEX IF NOT EXISTS journey_user ON ops_journey(user_id)')
    db.execute('CREATE TABLE IF NOT EXISTS ops_identity (visitor TEXT, user_id TEXT, created REAL, PRIMARY KEY(visitor,user_id))')
    db.execute('CREATE TABLE IF NOT EXISTS ops_task_details (task TEXT PRIMARY KEY, metadata TEXT, frames TEXT)')

def stamp(value):
    if isinstance(value, (int, float)): return value
    if hasattr(value, 'timestamp'): return value.timestamp()
    try: return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    except (ValueError, AttributeError, TypeError): return None

def record(action, visitor=None, user_id=None, task=None, details=None, created=None):
    """Best effort: metrics must not fail uploads, login, payment or feedback."""
    try:
        now = created if created is not None else time.time()
        with database() as db:
            init(db)
            # A result open is unique per report and viewer; other events are debounced.
            since = 0 if action in ('result_viewed','registered','claimed') else now-2
            if db.execute('SELECT 1 FROM ops_journey WHERE visitor IS ? AND user_id IS ? AND action=? AND task IS ? AND created>=?',
                          (visitor,user_id,action,task,since)).fetchone(): return
            db.execute('INSERT INTO ops_journey(visitor,user_id,action,task,created,details) VALUES (?,?,?,?,?,?)',
                       (visitor,user_id,action,task,now,json.dumps(details or {},default=str)))
            db.execute('DELETE FROM ops_journey WHERE created<?', (time.time()-90*86400,))
    except Exception:
        logging.getLogger(__name__).exception('Could not persist operational event')

def link(visitor, user):
    try:
        with database() as db:
            init(db)
            db.execute('INSERT OR IGNORE INTO ops_identity VALUES (?,?,?)', (visitor,user['id'],time.time()))
        record('account_linked',visitor,user['id'])
        created = stamp(user.get('created_at'))
        if created is not None and not user.get('is_local'):
            # Timestamp comes from verified auth provider, not the browser.
            record('registered',visitor,user['id'],created=created)
    except Exception:
        logging.getLogger(__name__).exception('Could not link operational identity')

def task_metadata(task, metadata=None, frames=None):
    try:
        with database() as db:
            init(db)
            db.execute('INSERT OR IGNORE INTO ops_task_details VALUES (?,NULL,NULL)', (task,))
            if metadata is not None: db.execute('UPDATE ops_task_details SET metadata=? WHERE task=?', (json.dumps(metadata),task))
            if frames is not None:
                clean=[{k:f.get(k) for k in ('phase','frame_number','timestamp','angles')} for f in frames]
                db.execute('UPDATE ops_task_details SET frames=? WHERE task=?', (json.dumps(clean),task))
    except Exception:
        logging.getLogger(__name__).exception('Could not store analysis diagnostics')

def result_file(task):
    root=settings.results_dir.resolve()
    path=(root/task/'result.json').resolve()
    if not path.is_relative_to(root) or path.parent == root: raise HTTPException(404,'Report not found')
    return path

def task_detail(task):
    with database() as db:
        init(db)
        row=db.execute('SELECT r.*,q.finished,q.error,q.frames AS frame_count,d.metadata,d.frames FROM reports r LEFT JOIN ops_quality q ON r.id=q.task LEFT JOIN ops_task_details d ON r.id=d.task WHERE r.id=?',(task,)).fetchone()
        if not row: raise HTTPException(404,'Report not found')
        data=dict(row);data.pop('ip',None)
        feedback=db.execute('SELECT helpful,accurate,created FROM ops_feedback WHERE task=?',(task,)).fetchone()
        data['feedback']=dict(feedback) if feedback else None
    data['metadata']=json.loads(data['metadata']) if data['metadata'] else {}
    frames=json.loads(data['frames']) if data['frames'] is not None else None
    path=result_file(task)
    data['media_available']=False
    if data['state']!='deleted' and (not data['expires'] or data['expires']>time.time()) and path.is_file():
        try:
            result=json.loads(path.read_text())
            if frames is None: frames=[{k:f.get(k) for k in ('phase','frame_number','timestamp','angles')} for f in result.get('key_frames',[])]
            data['media_available']=True
        except (OSError,ValueError): pass
    data['frames']=frames
    present={f['phase'] for f in frames} if frames is not None else None
    data['missing_phases']=[{'phase':k,'label':v} for k,v in PHASES.items() if k not in present] if present is not None else None
    data['elapsed_seconds']=round(data['finished']-data['created'],1) if data['finished'] else None
    data['diagnostic_note']='Missing means not detected in this clip; it may be cropped, occluded or intentionally omitted for insufficient evidence. It is not a form fault.'
    if data['state']=='failed' and not data['error']: data['error']='Failed or abandoned task; historical error detail unavailable.'
    return data

def overview(days):
    cutoff=time.time()-days*86400
    with database() as db:
        init(db)
        events=[dict(r) for r in db.execute('SELECT * FROM ops_journey WHERE created>=? ORDER BY created,id',(cutoff,))]
        reports=[dict(r) for r in db.execute('SELECT r.*,q.finished FROM reports r LEFT JOIN ops_quality q ON r.id=q.task WHERE r.created>=? ORDER BY r.created',(cutoff,))]
        detail={r['task']:json.loads(r['frames']) for r in db.execute('SELECT task,frames FROM ops_task_details WHERE frames IS NOT NULL')}
    for e in events: e['details']=json.loads(e['details'])
    visits={}
    for e in events:
        if e['action']=='visit' and e['visitor'] and e['visitor'] not in visits: visits[e['visitor']]=e
    labels=['访问','选择视频','开始分析','分析完成','查看结果','保存到账户','再次分析']
    stages=[set() for _ in labels]; registrations=set(); submitted=set(); comparisons=set()
    for v,visit in visits.items():
        stages[0].add(v); start=visit['created']
        selected=[e['created'] for e in events if e['visitor']==v and e['action']=='file_selected' and e['created']>=start]
        if not selected: continue
        stages[1].add(v)
        tasks=[r for r in reports if r['visitor']==v and r['created']>=min(selected)]
        if not tasks: continue
        stages[2].add(v)
        done=[r for r in tasks if r['state']=='completed' and r['finished'] is not None]
        if not done: continue
        stages[3].add(v)
        ids={r['id']:r for r in done}
        views=[e for e in events if e['action']=='result_viewed' and e['task'] in ids and e['created']>=ids[e['task']]['finished'] and (e['visitor']==v or e['user_id']==ids[e['task']]['owner'])]
        if not views: continue
        first_view=min(e['created'] for e in views); stages[4].add(v)
        if any(e['visitor']==v and e['action']=='registration_submitted' and e['created']>=first_view for e in events): submitted.add(v)
        if any(e['visitor']==v and e['action']=='registered' and e['created']>=first_view for e in events): registrations.add(v)
        claims=[e for e in events if e['action']=='claimed' and e['task'] in ids and e['created']>=first_view]
        if not claims: continue
        stages[5].add(v)
        claim=min(claims,key=lambda e:e['created'])
        again=[r for r in reports if r['owner']==claim['user_id'] and r['created']>claim['created'] and r['id'] not in ids]
        if again: stages[6].add(v)
        if any(e['action']=='comparison_viewed' and e['user_id']==claim['user_id'] and e['created']>=claim['created'] for e in events): comparisons.add(v)
    def breakdown(key):
        groups={}
        for v,e in visits.items():
            value=e['details'].get(key) or ('direct' if key=='source' else '(unknown)')
            groups.setdefault(value,set()).add(v)
        return [{'name':k,'counts':[len(group & s) for s in stages]} for k,group in groups.items()]
    missing={k:0 for k in PHASES}; anomalies=[]; measured=0
    for r in reports:
        frames=detail.get(r['id']); absent=None
        if frames is not None:
            measured+=1;present={f.get('phase') for f in frames};absent=[k for k in PHASES if k not in present]
            for k in absent: missing[k]+=1
        if r['state']=='failed' or absent or (r['state']=='processing' and time.time()-r['created']>3600):
            anomalies.append({'id':r['id'],'owner':r['owner'],'filename':r['filename'],'state':r['state'],'missing':absent,'stalled':r['state']=='processing'})
    return {'journey':[{'label':l,'count':len(s),'conversion':round(100*len(s)/len(stages[i-1]),1) if i and stages[i-1] else None} for i,(l,s) in enumerate(zip(labels,stages))],
            'registration_submitted':len(submitted),'registered_after_view':len(registrations),'comparison_accounts':len(comparisons),
            'sources':breakdown('source'),'landings':breakdown('landing'),'campaigns':breakdown('campaign'),
            'quality_measured':measured,'missing_summary':[{'phase':k,'label':PHASES[k],'count':v} for k,v in missing.items()],
            'anomalies':list(reversed(anomalies))[:100],'anomaly_count':len(anomalies),
            'accounts':[{'id':u,'analyses':sum(r['owner']==u for r in reports)} for u in sorted({r['owner'] for r in reports if r['owner']})]}

async def user_detail(user_id):
    from .db_service import db_service
    from .feedback_service import feedback_store
    with database() as db:
        init(db)
        reports=[dict(r) for r in db.execute('SELECT id,filename,state,created,visitor FROM reports WHERE owner=? ORDER BY created',(user_id,))]
        links=[dict(r) for r in db.execute('SELECT * FROM ops_identity WHERE user_id=?',(user_id,))]
        events=[dict(r) for r in db.execute('SELECT * FROM ops_journey WHERE user_id=? ORDER BY created',(user_id,))]
        # Only anonymous events before the explicit identity link are attributed retroactively.
        for linkrow in links:
            events.extend(dict(r) for r in db.execute('SELECT * FROM ops_journey WHERE visitor=? AND user_id IS NULL AND created<=?',(linkrow['visitor'],linkrow['created'])))
        surveys=[dict(r) for r in db.execute('SELECT f.* FROM ops_feedback f JOIN reports r ON r.id=f.task WHERE r.owner=?',(user_id,))]
        credits=[dict(r) for r in db.execute('SELECT * FROM credit_changes WHERE target=? ORDER BY created',(user_id,))]
    events=list({e['id']:e for e in events}.values())
    for e in events:e['details']=json.loads(e['details'])
    cloud={}; errors={}; profile=None
    if db_service.is_available():
        for table in ('analyses','payment_checkouts','user_subscriptions','user_credits'):
            try:
                rows=[]; offset=0
                while True:
                    batch=db_service.client.table(table).select('*').eq('user_id',user_id).range(offset,offset+499).execute().data or []
                    rows.extend(batch)
                    if len(batch)<500:break
                    offset+=500
                cloud[table]=rows
            except Exception: errors[table]='Unavailable; retry later'
        try:
            user=db_service.client.auth.admin.get_user_by_id(user_id).user
            if user: profile={'id':user.id,'email':user.email,'created_at':str(user.created_at)}
        except Exception: errors['profile']='Unavailable or local-only account'
    else: errors['cloud']='Cloud data unavailable; local records shown'
    reviews=[]
    try:
        for r in feedback_store.all():
            if r['owner'] in ('local:'+user_id,'supabase:'+user_id) and r['state']!='deleted':
                reviews.append({k:r.get(k) for k in ('id','created_at','filename','state','goal','problem','context','parent','practice','versions')})
    except Exception: errors['reviews']='Training feedback unavailable'
    timeline=[]
    def add(at,action,detail,task=None):
        at=stamp(at)
        if at is not None:timeline.append({'created':at,'action':action,'details':detail,'task':task})
    for e in events:add(e['created'],e['action'],e['details'],e['task'])
    for r in reports:add(r['created'],'analysis',{'filename':r['filename'],'state':r['state'],'trial':bool(r['visitor'])},r['id'])
    localids={r['id'] for r in reports}
    for r in cloud.get('analyses',[]):
        if r['id'] not in localids:add(r.get('created_at'),'legacy_analysis',{'state':r.get('status'),'filename':r.get('video_filename')},r['id'])
    for r in surveys:add(r['created'],'quality_feedback',{'helpful':bool(r['helpful']),'accurate':bool(r['accurate'])},r['task'])
    for r in credits:add(r['created'],'credit_adjusted',{k:r[k] for k in ('actor','before_balance','after_balance','reason')})
    for r in reviews:add(r['created_at'],'retest' if r['parent'] else 'training_feedback',r,r['id'])
    for r in cloud.get('payment_checkouts',[]):add(r.get('processed_at'),'payment_processed',{'checkout_id':r.get('checkout_id')})
    if profile and not any(e['action']=='registered' for e in events):add(profile.get('created_at'),'registered',{'source':'auth_provider'})
    return {'id':user_id,'profile':profile,'reports':reports,'timeline':sorted(timeline,key=lambda e:e['created']),
            'reviews':reviews,'surveys':surveys,'credit_changes':credits,'cloud':cloud,'errors':errors,
            'coverage':'Journey events retain 90 days. Missing events are unknown; payment records do not contain amount/refund details.'}
