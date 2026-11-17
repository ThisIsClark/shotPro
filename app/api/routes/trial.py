"""Anonymous trial and automatic account handoff."""
import time
from fastapi import APIRouter, Depends, Request, Response
from ..deps import get_current_user_required
from ...services.trial_service import trial_store

router = APIRouter(prefix='/trial', tags=['trial'])

@router.get('/status')
async def trial_status(request: Request, response: Response):
    trial_store.maintenance()
    vid = trial_store.visitor(request, response)
    response.headers['Cache-Control'] = 'no-store'
    with trial_store.db() as db:
        row = db.execute("SELECT id,state FROM reports WHERE visitor=? AND owner IS NULL AND expires>? AND state IN ('completed','processing') ORDER BY created DESC LIMIT 1", (vid, time.time())).fetchone()
    return {'credits_remaining': trial_store.remaining(vid), 'is_unlimited': False, 'max_duration': 10,
            'task_id': row['id'] if row else None, 'state': row['state'] if row else None}

@router.post('/claim')
async def claim_trial(request: Request, response: Response, user=Depends(get_current_user_required)):
    vid = trial_store.visitor(request, response)
    ids = trial_store.claim(vid, user['id'])
    from ...services.admin_insights import link, record
    link(vid, user)
    for task in ids: record('claimed', vid, user['id'], task)
    # Images/video elements cannot send Bearer headers. Short-lived, signed media-only cookie.
    value = user['id'] + ':' + str(int(time.time()+3600))
    response.set_cookie('shot_media', value + ':' + trial_store.sign(value), max_age=3600,
                        httponly=True, secure=request.url.scheme == 'https', samesite='lax')
    return {'claimed': ids}

@router.post('/logout')
async def clear_media_session(response: Response):
    response.delete_cookie('shot_media')
    return {'ok': True}


from pydantic import BaseModel, StrictBool
from ..deps import get_current_user_optional

class QualityFeedback(BaseModel):
    helpful: StrictBool
    accurate: StrictBool

@router.post('/reports/{task_id}/feedback')
async def quality_feedback(task_id: str, data: QualityFeedback, request: Request,
                           user=Depends(get_current_user_optional)):
    from .upload import authorize_report
    from ...services.admin_metrics import database
    from fastapi import HTTPException
    await authorize_report(task_id, request, user)
    row = trial_store.get(task_id)
    if not row or row['state'] != 'completed':
        raise HTTPException(409, 'Feedback requires a completed report.')
    with database() as db:
        db.execute('INSERT INTO ops_feedback VALUES (?,?,?,?) ON CONFLICT(task) DO UPDATE SET helpful=excluded.helpful,accurate=excluded.accurate',
                   (task_id, int(data.helpful), int(data.accurate), time.time()))
    return {'ok': True}
