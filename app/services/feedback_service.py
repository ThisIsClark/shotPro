"""Persistent, single-host pilot feedback store. Media never lives in /results."""
import json
import secrets
import shutil
import sqlite3
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from ..config import settings


def subject(user):
    return ('local:' if user.get('is_local') else 'supabase:') + str(user['id'])


class FeedbackStore:
    def __init__(self, root=None):
        self.root = Path(root or settings.feedback_dir)

    @contextmanager
    def transaction(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.root / 'feedback.sqlite3', timeout=20) as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS grants (owner TEXT PRIMARY KEY, remaining INTEGER NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            yield db

    def get(self, task_id):
        with self.transaction() as db:
            row = db.execute('SELECT payload FROM records WHERE id=?', (task_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def all(self):
        with self.transaction() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT payload FROM records ORDER BY rowid DESC')]

    def change(self, task_id, fn):
        with self.transaction() as db:
            row = db.execute('SELECT payload FROM records WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Feedback record not found')
            data = json.loads(row[0])
            fn(data)
            db.execute('UPDATE records SET payload=? WHERE id=?', (json.dumps(data), task_id))
            return data

    def capture(self, task_id, user, path, filename, duration=0):
        folder = self.root / task_id
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / ('original' + Path(path).suffix.lower())
        if Path(path).resolve() != source.resolve():
            shutil.copy2(path, source)
        record = dict(id=task_id, owner=subject(user), filename=filename,
                      created_at=time.time(), original=source.name, duration=duration,
                      state='available', analysis_state='pending', result=None, goal='', context='',
                      problem='', revision=0, draft={}, versions=[], shares=[], parent=None,
                      practice=None, thread_id=task_id, keyframes=[], author='', error=None)
        with self.transaction() as db:
            db.execute('INSERT INTO records VALUES (?,?)', (task_id, json.dumps(record)))
        return record

    def prepare_playback(self, task_id):
        r = self.get(task_id)
        if not r or r['state'] == 'deleted' or not shutil.which('ffmpeg'):
            return
        folder = self.root / task_id
        target = folder / 'playback.mp4'
        if target.exists():
            return
        temporary = folder / 'playback-tmp.mp4'
        try:
            process = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(folder / r['original']),
                                      '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                                      str(temporary)], capture_output=True, timeout=60)
            if process.returncode == 0:
                temporary.replace(target)
        except (OSError, subprocess.TimeoutExpired):
            pass  # Original remains available; inference/review must not be lost.
        finally:
            temporary.unlink(missing_ok=True)

    def snapshot(self, task_id, result, source_dir):
        record = self.get(task_id)
        if not record or record['state'] == 'deleted':
            return
        folder = self.root / task_id
        frames = []
        for frame in result.get('key_frames', []):
            name = Path(frame.get('image_url', '')).name
            src = Path(source_dir) / name
            if src.is_file():
                if src.resolve() != (folder / name).resolve():
                    shutil.copy2(src, folder / name)
                frames.append({**frame, 'image_url': None, 'asset': name})
        clean = {k: result.get(k) for k in ('duration', 'fps', 'total_frames')}
        # Observations are stored without legacy publicly-addressed image URLs.
        clean['observations'] = [{k: i.get(k) for k in ('issue_type', 'detected', 'description_en', 'skipped', 'skip_reason')}
                                 for i in result.get('coordination_issues', [])]
        def update(r):
            r.update(result=clean, keyframes=frames, analysis_state='completed', error=None)
            if not r['duration']:
                r['duration'] = result.get('duration', 0)
        self.change(task_id, update)

    def grant(self, owner, count):
        with self.transaction() as db:
            db.execute('INSERT INTO grants VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET remaining=excluded.remaining', (owner, count))

    def request(self, task_id, user, goal, context, problem):
        with self.transaction() as db:
            row = db.execute('SELECT payload FROM records WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Upload the original video first')
            r = json.loads(row[0])
            self.authorize(r, user)
            if r['state'] != 'available':
                return r
            if user.get('role') != 'admin':
                grant = db.execute('SELECT remaining FROM grants WHERE owner=?', (r['owner'],)).fetchone()
                if not grant or grant[0] < 1:
                    raise HTTPException(403, 'Human feedback is invitation-only. Ask the reviewer for pilot access.')
                db.execute('UPDATE grants SET remaining=remaining-1 WHERE owner=?', (r['owner'],))
            r.update(goal=goal, context=context, problem=problem, state='waiting')
            db.execute('UPDATE records SET payload=? WHERE id=?', (json.dumps(r), task_id))
            return r

    @staticmethod
    def authorize(r, user, admin=False):
        if not r or r.get('state') == 'deleted':
            raise HTTPException(404, 'Record not found')
        if admin and user.get('role') != 'admin':
            raise HTTPException(403, 'Reviewer access required')
        if r['owner'] != subject(user) and user.get('role') != 'admin':
            raise HTTPException(404, 'Record not found')

    def recover(self):
        for r in self.all():
            if r['analysis_state'] in ('pending', 'processing'):
                self.change(r['id'], lambda x: x.update(analysis_state='failed', error='Analysis interrupted. Retry analysis; your video and feedback are saved.'))
            reservation = r.get('followup')
            if reservation and not self.get(reservation['id']):
                # An interrupted upload can be retried with the existing reservation.
                shutil.rmtree(self.root / reservation['id'], ignore_errors=True)
            if r['state'] == 'deleted':
                shutil.rmtree(self.root / r['id'], ignore_errors=True)


feedback_store = FeedbackStore()
