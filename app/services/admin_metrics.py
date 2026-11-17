"""Operational metrics on the same persistent volume as private reports.
No raw IP or video content is retained here. Historical missing events stay unknown.
"""
import json
import time
from collections import Counter
from contextlib import contextmanager
from .trial_service import trial_store

@contextmanager
def database():
    with trial_store.db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS ops_events (visitor TEXT, action TEXT, created REAL, source TEXT)')
        db.execute('CREATE INDEX IF NOT EXISTS ops_event_time ON ops_events(created)')
        db.execute('CREATE TABLE IF NOT EXISTS ops_quality (task TEXT PRIMARY KEY, finished REAL, error TEXT, frames INTEGER)')
        db.execute('CREATE TABLE IF NOT EXISTS credit_changes (created REAL, actor TEXT, target TEXT, before_balance INTEGER, after_balance INTEGER, reason TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS ops_feedback (task TEXT PRIMARY KEY, helpful INTEGER, accurate INTEGER, created REAL)')
        yield db

def event(visitor, action, source='direct'):
    with database() as db:
        # Bound storage and debounce repeated client events, without counting page refreshes as people.
        db.execute('DELETE FROM ops_events WHERE created<?', (time.time()-90*86400,))
        if not db.execute('SELECT 1 FROM ops_events WHERE visitor=? AND action=? AND created>?', (visitor, action, time.time()-2)).fetchone():
            db.execute('INSERT INTO ops_events VALUES (?,?,?,?)', (visitor, action, time.time(), source[:80]))

def quality(task, error=None, frames=None):
    try:
        with database() as db:
            db.execute('INSERT OR REPLACE INTO ops_quality VALUES (?,?,?,?)', (task, time.time(), str(error)[:500] if error else None, frames))
    except Exception:
        # Observability must never turn a successful analysis into a failed task.
        import logging
        logging.getLogger(__name__).exception('Could not record analysis quality')

def snapshot(days):
    cutoff = time.time()-days*86400
    with database() as db:
        rows = [dict(r) for r in db.execute('SELECT r.*,q.finished,q.error,q.frames FROM reports r LEFT JOIN ops_quality q ON r.id=q.task WHERE r.created>=? ORDER BY r.created DESC', (cutoff,))]
        events = [dict(r) for r in db.execute('SELECT * FROM ops_events WHERE created>=? ORDER BY created', (cutoff,))]
        feedback = [dict(r) for r in db.execute('SELECT * FROM ops_feedback WHERE created>=?', (cutoff,))]
        changes = [dict(r) for r in db.execute('SELECT * FROM credit_changes ORDER BY created DESC LIMIT 100')]
    sources = {}
    views = {}
    for e in events:
        if e['action']=='visit' and e['visitor'] not in views:
            views[e['visitor']]=e['created']; sources[e['visitor']]=e['source']
    stages = [set(views), set(), set(), set()]
    for r in rows:
        v = r['visitor']
        if v in views and r['created']>=views[v]:
            stages[1].add(v)
            if r['state']=='completed':
                stages[2].add(v)
                if r['owner']: stages[3].add(v)
    channels=[]
    for source in sorted(set(sources.values())):
        cohort={v for v,s in sources.items() if s==source}
        channels.append({'source':source, 'visitors':len(cohort), 'started':len(cohort & stages[1]), 'completed':len(cohort & stages[2]), 'saved':len(cohort & stages[3])})
    completed=[r for r in rows if r['state']=='completed']
    durations=[r['finished']-r['created'] for r in rows if r['finished'] and r['state']=='completed']
    owners=Counter(r['owner'] for r in completed if r['owner'])
    return {'days':days, 'total':len(rows), 'completed':len(completed), 'failed':sum(r['state']=='failed' for r in rows),
            'processing':sum(r['state']=='processing' for r in rows), 'anonymous_started':sum(bool(r['visitor']) for r in rows),
            'saved_trials':sum(bool(r['visitor'] and r['owner']) for r in rows),
            'repeat_accounts':sum(n>=2 for n in owners.values()), 'average_seconds':round(sum(durations)/len(durations),1) if durations else None,
            'measured_durations':len(durations), 'channels':channels,
            'funnel':[{'label':label,'count':len(stage)} for label,stage in zip(['Visitors','Started a trial','Completed a trial','Saved to account'],stages)],
            'recent':[{'id':r['id'],'filename':r['filename'],'state':r['state'],'created':r['created'],'error':r['error'],'frames':r['frames'],'type':'Trial' if r['visitor'] else 'Account'} for r in rows[:100]],
            'credit_changes':changes, 'feedback':{'responses':len(feedback), 'helpful':sum(r['helpful'] for r in feedback), 'accurate':sum(r['accurate'] for r in feedback)}}
