"""Human feedback and follow-up pilot; private media and versioned reviews."""
import hashlib
import json
import mimetypes
import secrets
import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal, Optional
from uuid import uuid4

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from jose import jwt, JWTError
from pydantic import BaseModel, Field, model_validator

from ..deps import get_current_user_required, require_admin
from ...config import settings
from ...services.feedback_service import feedback_store as store, subject

router = APIRouter(prefix='/feedback', tags=['feedback'])


class RequestFeedback(BaseModel):
    goal: Literal['quicker_release', 'range', 'consistency', 'other']
    context: Literal['stationary', 'catch_and_shoot', 'off_dribble', 'other']
    problem: str = Field(min_length=1, max_length=1000)


class Review(BaseModel):
    revision: int = Field(ge=0)
    observation: str = Field(default='', max_length=3000)
    focus: str = Field(default='', max_length=1000)
    drill: str = Field(default='', max_length=3000)
    retest: str = Field(default='', max_length=2000)
    criteria: str = Field(default='', max_length=1000)
    evidence_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    author: str = Field(default='', max_length=100)
    frames: list[dict] = Field(default_factory=list, max_length=12)


class Practice(BaseModel):
    completion: Literal['done', 'partial', 'not_done']
    feeling: Literal['smoother', 'same', 'harder', 'unsure']
    notes: str = Field(default='', max_length=2000)
    attempts: Optional[int] = Field(default=None, gt=0, le=100000)
    makes: Optional[int] = Field(default=None, ge=0)
    conditions_changed: bool = False
    conditions_note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def valid_counts(self):
        if (self.attempts is None) != (self.makes is None):
            raise ValueError('Enter both attempts and makes, or leave both empty')
        if self.makes is not None and self.makes > self.attempts:
            raise ValueError('Makes cannot exceed attempts')
        if self.conditions_changed and not self.conditions_note.strip():
            raise ValueError('Describe the changed conditions')
        return self


def owned(task_id, user):
    r = store.get(task_id)
    store.authorize(r, user)
    return r


def public_record(r, admin=False):
    keys = ['id', 'filename', 'created_at', 'duration', 'state', 'analysis_state', 'result',
            'goal', 'context', 'problem', 'parent', 'practice', 'thread_id', 'error']
    out = {k: r.get(k) for k in keys}
    out['video'] = f"/api/v1/feedback/media/{r['id']}/{r['original']}"
    out['keyframes'] = r['keyframes']
    out['review'] = r['versions'][-1] if r['versions'] else None
    out['versions'] = [{'version': v['version'], 'published_at': v['published_at']} for v in r['versions']]
    out['share_active'] = any(not s['revoked'] for s in r['shares'])
    followup_id = (r.get('followup') or {}).get('id')
    out['followup_id'] = followup_id if followup_id and store.get(followup_id) else None
    if admin:
        out.update(draft=r['draft'], revision=r['revision'], owner=r['owner'])
    return out


@router.post('/media-session')
def media_session(request: Request, response: Response, user=Depends(get_current_user_required)):
    # Purpose-specific token deliberately has no `sub`: cannot become a login token.
    media_user = {k: user.get(k) for k in ('id', 'role', 'is_local')}
    token = jwt.encode({'media_user': media_user, 'exp': int(time.time()) + 3600, 'purpose': 'feedback-media'}, settings.jwt_secret, algorithm='HS256')
    response.set_cookie('feedback_media', token, max_age=3600, httponly=True,
                        secure=request.url.scheme == 'https', samesite='strict', path='/api/v1/feedback/media')
    return {'ok': True}


@router.delete('/media-session')
def clear_media_session(response: Response):
    response.delete_cookie('feedback_media', path='/api/v1/feedback/media')
    return {'ok': True}


@router.get('')
def listing(user=Depends(get_current_user_required)):
    is_admin = user.get('role') == 'admin'
    return {'admin': is_admin, 'subject': subject(user), 'items': [public_record(r, is_admin) for r in store.all()
            if r['state'] != 'deleted' and (r['owner'] == subject(user) or (is_admin and r['state'] != 'available'))]}


class Grant(BaseModel):
    owner: str = Field(min_length=3, max_length=200)
    count: int = Field(ge=0, le=100)


@router.post('/grants')
def grant(body: Grant, user=Depends(require_admin)):
    if not body.owner.startswith(('local:', 'supabase:')):
        raise HTTPException(422, 'Use the pilot ID shown in the user’s Training page')
    store.grant(body.owner, body.count)
    return {'ok': True}


@router.get('/tasks/{task_id}')
def detail(task_id: str, user=Depends(get_current_user_required)):
    r = owned(task_id, user)
    out = public_record(r, user.get('role') == 'admin')
    out['timeline'] = [public_record(x) for x in store.all() if x['thread_id'] == r['thread_id'] and x['state'] != 'deleted']
    if r['parent']:
        parent = owned(r['parent']['id'], user)
        out['previous'] = public_record(parent)
        out['previous']['review'] = next(v for v in parent['versions'] if v['version'] == r['parent']['version'])
    return out


@router.post('/tasks/{task_id}/request')
def request_feedback(task_id: str, body: RequestFeedback, user=Depends(get_current_user_required)):
    if not body.problem.strip():
        raise HTTPException(422, 'Describe what you want to improve')
    r = store.request(task_id, user, body.goal, body.context, body.problem.strip())
    return public_record(r)


@router.put('/tasks/{task_id}/draft')
def save_draft(task_id: str, body: Review, user=Depends(require_admin)):
    def update(r):
        store.authorize(r, user, admin=True)
        if r['state'] == 'available':
            raise HTTPException(409, 'Request feedback before editing')
        if body.revision != r['revision']:
            raise HTTPException(409, 'Another edit was saved. Reload before saving again.')
        if body.evidence_seconds > r['duration']:
            raise HTTPException(422, 'Evidence time is outside the video')
        allowed = {x['asset'] for x in r['keyframes']} | set(r.get('manual_frames', []))
        for f in body.frames:
            if f.get('asset') not in allowed or not isinstance(f.get('phase'), str) or len(f['phase']) > 80:
                raise HTTPException(422, 'Invalid keyframe')
            t = f.get('timestamp')
            if not isinstance(t, (int, float)) or not 0 <= t <= r['duration']:
                raise HTTPException(422, 'Invalid keyframe time')
        r.update(draft=body.model_dump(exclude={'revision'}), revision=r['revision'] + 1, state='draft')
    return public_record(store.change(task_id, update), True)


class Publish(BaseModel):
    revision: int


@router.post('/tasks/{task_id}/publish')
def publish(task_id: str, body: Publish, user=Depends(require_admin)):
    def update(r):
        store.authorize(r, user, admin=True)
        if r['versions'] and r['versions'][-1]['revision'] == body.revision and r['revision'] == body.revision:
            return
        if body.revision != r['revision']:
            raise HTTPException(409, 'The draft changed. Reload before publishing.')
        d = r['draft']
        for name in ('observation', 'focus', 'drill', 'retest', 'criteria', 'author'):
            if not d.get(name, '').strip():
                raise HTTPException(422, f'Complete {name} before publishing')
        if r['duration'] <= 0 or not (store.root / r['id'] / r['original']).is_file():
            raise HTTPException(409, 'Original video is missing. Upload it again.')
        r['versions'].append({**d, 'version': len(r['versions']) + 1, 'revision': r['revision'],
                              'author_subject': subject(user), 'published_at': time.time()})
        r['state'] = 'published'
    return public_record(store.change(task_id, update), True)


class Frame(BaseModel):
    seconds: float = Field(ge=0, allow_inf_nan=False)


@router.post('/tasks/{task_id}/frame')
def frame(task_id: str, body: Frame, user=Depends(require_admin)):
    r = owned(task_id, user)
    if body.seconds >= r['duration']:
        raise HTTPException(422, 'Choose a time before the end of the video')
    cap = cv2.VideoCapture(str(store.root / task_id / r['original']))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, body.seconds * 1000)
        ok, image = cap.read()
        actual = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if not ok:
            raise HTTPException(422, 'Could not decode that frame')
        name = 'manual-' + secrets.token_hex(8) + '.jpg'
        if not cv2.imwrite(str(store.root / task_id / name), image):
            raise HTTPException(500, 'Could not save frame')
    finally:
        cap.release()
    store.change(task_id, lambda x: x.setdefault('manual_frames', []).append(name))
    return {'asset': name, 'timestamp': actual, 'phase': 'Observation', 'angles': None}


def run_followup(task_id):
    from ...services.analysis_service import AnalysisService, AnalysisConfig
    r = store.get(task_id)
    if not r or r['state'] == 'deleted':
        return
    store.change(task_id, lambda x: x.update(analysis_state='processing', error=None))
    try:
        with AnalysisService(AnalysisConfig(output_dir=store.root, shooting_hand=r.get('shooting_hand', 'right'))) as service:
            result = service.analyze_video(store.root / task_id / r['original'], task_id=task_id).to_dict()
        store.snapshot(task_id, result, store.root / task_id)
    except Exception:
        store.change(task_id, lambda x: x.update(analysis_state='failed', error='Automatic analysis could not finish. Your video is saved for human review.'))
    finally:
        if store.get(task_id)['state'] == 'deleted':
            shutil.rmtree(store.root / task_id, ignore_errors=True)


async def save_video(file, folder):
    from .upload import validate_video_file
    validate_video_file(file)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('original' + Path(file.filename or '.mp4').suffix.lower())
    total = 0
    try:
        with path.open('wb') as stream:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.max_video_size_mb * 1024 * 1024:
                    raise HTTPException(413, 'Video exceeds the upload size limit')
                stream.write(chunk)
        cap = cv2.VideoCapture(str(path))
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps if fps else 0
            ok, _ = cap.read()
        finally:
            cap.release()
        if not ok or not 0 < duration <= settings.max_video_duration_seconds:
            raise HTTPException(422, f'Upload a playable video of at most {settings.max_video_duration_seconds} seconds')
        # Browser-compatible playback, while original is kept for analysis.
        if shutil.which('ffmpeg'):
            converted = folder / 'playback.mp4'
            proc = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-an', '-c:v', 'libx264',
                                   '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(converted)], capture_output=True, timeout=60)
            if proc.returncode:
                converted.unlink(missing_ok=True)
        return path, duration
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise


@router.post('/tasks/{task_id}/followup')
async def followup(task_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...),
                   practice: str = Form(...), version: int = Form(...), key: str = Form(...),
                   user=Depends(get_current_user_required)):
    from pydantic import ValidationError
    parent = owned(task_id, user)
    if parent['parent'] and user.get('role') != 'admin':
        raise HTTPException(403, 'Your included pilot follow-up is complete. Contact your reviewer for another round.')
    if not any(v['version'] == version for v in parent['versions']):
        raise HTTPException(409, 'Choose a published feedback version')
    if not 8 <= len(key) <= 100:
        raise HTTPException(422, 'Invalid submission key')
    try:
        log = Practice.model_validate_json(practice).model_dump()
    except ValidationError as e:
        raise HTTPException(422, 'Check the practice log: ' + str(e))
    # Reserve one included follow-up atomically. Retries with the same key reuse it.
    child_id = str(uuid4())
    def reserve(r):
        existing = r.get('followup')
        if existing and existing['key'] != key:
            raise HTTPException(409, 'A follow-up already exists. Open it in your training history.')
        if not existing:
            r['followup'] = {'key': key, 'id': child_id}
    parent = store.change(task_id, reserve)
    child_id = parent['followup']['id']
    existing = store.get(child_id)
    if existing:
        return public_record(existing)
    # A per-key reservation rejects concurrent in-flight requests, without double charges.
    folder = store.root / child_id
    try:
        folder.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise HTTPException(409, 'Upload already in progress. Please retry shortly.')
    path, duration = await save_video(file, folder)
    store.capture(child_id, {'id': parent['owner'].split(':', 1)[1], 'is_local': parent['owner'].startswith('local:')}, path, file.filename, duration)
    def finish(r):
        r.update(parent={'id': task_id, 'version': version}, practice=log, thread_id=parent['thread_id'],
                 goal=parent['goal'], context=parent['context'], problem=parent['problem'], state='waiting',
                 shooting_hand=parent.get('shooting_hand', 'right'))
    result = store.change(child_id, finish)
    background_tasks.add_task(run_followup, child_id)
    return public_record(result)


@router.post('/tasks/{task_id}/retry')
def retry(task_id: str, background_tasks: BackgroundTasks, user=Depends(require_admin)):
    r = owned(task_id, user)
    if r['analysis_state'] != 'failed':
        raise HTTPException(409, 'Only failed analyses can be retried')
    def claim(x):
        if x['analysis_state'] != 'failed':
            raise HTTPException(409, 'Analysis is already queued')
        x.update(analysis_state='processing')
    store.change(task_id, claim)
    background_tasks.add_task(run_followup, task_id)
    return {'ok': True}


@router.post('/tasks/{task_id}/shares')
def share(task_id: str, user=Depends(get_current_user_required)):
    r = owned(task_id, user)
    if r['owner'] != subject(user):
        raise HTTPException(403, 'Only the video owner can enable sharing')
    if not r['versions']:
        raise HTTPException(409, 'Publish feedback first')
    token = secrets.token_urlsafe(32)
    store.change(task_id, lambda x: x['shares'].append({'hash': hashlib.sha256(token.encode()).hexdigest(),
                 'version': x['versions'][-1]['version'], 'revoked': False}))
    # Fragment avoids sending the share secret in the page URL to access logs.
    return {'url': '/feedback-share#' + token}


@router.delete('/tasks/{task_id}/shares')
def revoke(task_id: str, user=Depends(get_current_user_required)):
    r = owned(task_id, user)
    if r['owner'] != subject(user):
        raise HTTPException(403, 'Only the owner can revoke sharing')
    def update(x):
        for s in x['shares']:
            s['revoked'] = True
    store.change(task_id, update)
    return {'ok': True}


def shared(token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    for r in store.all():
        if r['state'] == 'deleted':
            continue
        for s in r['shares']:
            if not s['revoked'] and secrets.compare_digest(s['hash'], digest):
                return r, next(v for v in r['versions'] if v['version'] == s['version'])
    raise HTTPException(404, 'This feedback link is unavailable or has been revoked')


class ShareToken(BaseModel):
    token: str = Field(min_length=30, max_length=100)


@router.post('/shared')
def shared_view(body: ShareToken, request: Request, response: Response):
    r, v = shared(body.token)
    # Isolated cookie authorizes only this published snapshot's media, not account APIs.
    response.set_cookie('feedback_share', body.token, httponly=True, secure=request.url.scheme == 'https',
                        samesite='strict', max_age=3600, path='/api/v1/feedback/shared-media')
    response.headers['Cache-Control'] = 'no-store'
    return {'id': r['id'], 'goal': r['goal'], 'problem': r['problem'], 'review': {k: value for k, value in v.items() if k not in ('author_subject', 'revision')},
            'video': f"/api/v1/feedback/shared-media/{r['id']}/{r['original']}",
            'duration': r['duration']}


def media_response(r, asset, request, allowed_frames=None):
    allowed = {r['original'], 'playback.mp4'} | {f['asset'] for f in (allowed_frames if allowed_frames is not None else r['keyframes'])}
    if allowed_frames is None:
        allowed |= set(r.get('manual_frames', []))
    if asset not in allowed or Path(asset).name != asset:
        raise HTTPException(404, 'Media not found')
    path = store.root / r['id'] / asset
    if asset == r['original'] and (path.parent / 'playback.mp4').exists():
        path = path.parent / 'playback.mp4'
    if not path.is_file():
        raise HTTPException(404, 'Media unavailable; upload the video again')
    size = path.stat().st_size
    start, end, status = 0, size - 1, 200
    header = request.headers.get('range')
    if header:
        try:
            unit, value = header.split('=')
            left, right = value.split('-')
            if unit != 'bytes' or ',' in value:
                raise ValueError()
            start = int(left) if left else max(0, size - int(right))
            end = min(int(right), size - 1) if left and right else size - 1
            if not 0 <= start <= end < size:
                raise ValueError()
            status = 206
        except ValueError:
            raise HTTPException(416, 'Invalid byte range', headers={'Content-Range': f'bytes */{size}'})
    def chunks():
        with path.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                data = stream.read(min(65536, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data
    headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(end-start+1), 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'}
    if status == 206:
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'
    return StreamingResponse(chunks(), status_code=status, headers=headers, media_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')


@router.get('/media/{task_id}/{asset}')
def media(task_id: str, asset: str, request: Request):
    try:
        payload = jwt.decode(request.cookies.get('feedback_media', ''), settings.jwt_secret, algorithms=['HS256'])
        if payload.get('purpose') != 'feedback-media':
            raise ValueError()
        user = payload['media_user']
    except (JWTError, ValueError, KeyError):
        raise HTTPException(401, 'Open your training page again to refresh video access')
    return media_response(owned(task_id, user), asset, request)


@router.get('/shared-media/{task_id}/{asset}')
def shared_media(task_id: str, asset: str, request: Request):
    r, version = shared(request.cookies.get('feedback_share', ''))
    if r['id'] != task_id:
        raise HTTPException(404, 'Media not found')
    return media_response(r, asset, request, allowed_frames=version.get('frames', []))


@router.delete('/tasks/{task_id}')
def delete(task_id: str, user=Depends(get_current_user_required)):
    r = owned(task_id, user)
    if r['owner'] != subject(user):
        raise HTTPException(403, 'Only the owner can delete this training thread')
    for item in store.all():
        if item['thread_id'] == r['thread_id']:
            store.change(item['id'], lambda x: x.update(state='deleted', shares=[]))
            shutil.rmtree(store.root / item['id'], ignore_errors=True)
    return {'ok': True}


@router.post('/tasks/{task_id}/restore-video')
async def restore_video(task_id: str, file: UploadFile = File(...), user=Depends(get_current_user_required)):
    """Attach a missing original to an owned legacy analysis, never claim by ID alone."""
    from .upload import task_store
    from ...services.db_service import db_service
    from ...services.supabase_client import is_supabase_enabled
    from uuid import UUID
    try:
        UUID(task_id)
    except ValueError:
        raise HTTPException(404, 'Analysis not found')
    existing = store.get(task_id)
    if existing:
        store.authorize(existing, user)
        raise HTTPException(409, 'A video is already saved. Open Training to continue.')
    analysis = await db_service.get_analysis(task_id) if is_supabase_enabled() and db_service.is_available() else None
    from ...services.trial_service import trial_store
    saved = trial_store.get(task_id)
    owns_saved = saved and saved['owner'] == user['id'] and saved['state'] != 'deleted'
    if not owns_saved and user.get('role') != 'admin' and (not analysis or str(analysis.get('user_id')) != str(user['id'])):
        raise HTTPException(404, 'Analysis not found')
    result_path = settings.results_dir / task_id / 'result.json'
    if not result_path.exists() and not analysis and task_id not in task_store:
        raise HTTPException(404, 'Analysis not found')
    folder = store.root / task_id
    if folder.exists():
        raise HTTPException(409, 'Video upload already in progress')
    folder.mkdir(parents=True)
    path, duration = await save_video(file, folder)
    r = store.capture(task_id, user, path, file.filename, duration)
    # Old measurements may refer to a different edit: run fresh analysis on replacement.
    store.change(task_id, lambda x: x.update(analysis_state='failed', error='Original attached. Reviewer can run analysis on this video.'))
    return public_record(r)
