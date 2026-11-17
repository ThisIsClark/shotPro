"""Durable anonymous quotas and report ownership (single persistent volume)."""
import hashlib
import hmac
import secrets
import sqlite3
import time
from contextlib import contextmanager
from fastapi import HTTPException
from ..config import settings

COOKIE = 'shot_visitor'

class TrialStore:
    def __init__(self, path=None):
        self.path = path

    @contextmanager
    def db(self):
        path = self.path or settings.trial_db_path
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=20)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute('CREATE TABLE IF NOT EXISTS visitors (id TEXT PRIMARY KEY, used INTEGER DEFAULT 0)')
            conn.execute('''CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, visitor TEXT,
                owner TEXT, filename TEXT, state TEXT, created REAL, expires REAL, ip TEXT)''')
            conn.commit()
            yield conn
            conn.commit()
        finally:
            conn.close()

    def visitor(self, request, response=None):
        token = request.cookies.get(COOKIE, '')
        parts = token.split('.')
        valid = len(parts) == 2 and len(parts[0]) == 64 and hmac.compare_digest(parts[1], self.sign(parts[0]))
        if valid:
            return parts[0]
        if response is None:
            raise HTTPException(401, 'Start your free trial from this browser first.')
        vid = secrets.token_hex(32)
        response.set_cookie(COOKIE, vid + '.' + self.sign(vid), max_age=365*86400,
                            httponly=True, secure=request.url.scheme == 'https', samesite='lax')
        return vid

    def sign(self, value):
        return hmac.new(settings.jwt_secret.encode(), value.encode(), hashlib.sha256).hexdigest()

    def remaining(self, vid):
        with self.db() as db:
            row = db.execute('SELECT used FROM visitors WHERE id=?', (vid,)).fetchone()
            active = db.execute("SELECT 1 FROM reports WHERE visitor=? AND state='processing'", (vid,)).fetchone()
            return 0 if active or (row and row['used']) else 1

    def reserve(self, task, vid, owner, filename, ip):
        now = time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not owner:
                db.execute('INSERT OR IGNORE INTO visitors(id) VALUES (?)', (vid,))
                used = db.execute('SELECT used FROM visitors WHERE id=?', (vid,)).fetchone()['used']
                active = db.execute("SELECT 1 FROM reports WHERE visitor=? AND state='processing'", (vid,)).fetchone()
                if used or active:
                    raise HTTPException(403, 'Your free trial is used or in progress. Sign in to continue.')
                # Count attempts, including failures, to cap expensive retry abuse.
                day = now - now % 86400
                count = db.execute('SELECT COUNT(*) FROM reports WHERE visitor IS NOT NULL AND created>=?', (day,)).fetchone()[0]
                recent = db.execute('SELECT COUNT(*) FROM reports WHERE ip=? AND visitor IS NOT NULL AND created>?', (ip, now-3600)).fetchone()[0]
                if count >= settings.trial_daily_limit or recent >= settings.trial_ip_hourly_limit:
                    raise HTTPException(429, 'Free trials are temporarily busy. Please sign in or try later.')
            db.execute('INSERT INTO reports VALUES (?,?,?,?,?,?,?,?)',
                       (task, vid, owner, filename, 'processing', now, None if owner else now+86400, ip))

    def get(self, task):
        with self.db() as db:
            row = db.execute('SELECT * FROM reports WHERE id=?', (task,)).fetchone()
            return dict(row) if row else None

    def finish(self, task, success):
        with self.db() as db:
            row = db.execute('SELECT * FROM reports WHERE id=?', (task,)).fetchone()
            if not row or row['state'] != 'processing': return
            db.execute("UPDATE reports SET state=? WHERE id=? AND state='processing'", ('completed' if success else 'failed', task))
            if row['visitor']:
                used = db.execute("SELECT 1 FROM reports WHERE visitor=? AND state='completed'", (row['visitor'],)).fetchone()
                db.execute('UPDATE visitors SET used=? WHERE id=?', (int(bool(used)), row['visitor']))

    def authorize(self, task, request, user=None):
        row = self.get(task)
        if not row: return False  # Legacy records are checked by their original owner separately.
        if row['state'] == 'deleted' or (row['expires'] and row['expires'] < time.time()):
            raise HTTPException(404, 'This temporary report has expired.')
        if row['owner']:
            if not user or user['id'] != row['owner']:
                raise HTTPException(404, 'Report not found.')
        elif self.visitor(request) != row['visitor']:
            raise HTTPException(404, 'Report not found.')
        return True

    def claim(self, vid, owner):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT id FROM reports WHERE visitor=? AND owner IS NULL AND expires>? AND state!='deleted'", (vid, time.time())).fetchall()
            db.execute("UPDATE reports SET owner=?,expires=NULL WHERE visitor=? AND owner IS NULL AND expires>? AND state!='deleted'", (owner, vid, time.time()))
            return [r['id'] for r in rows]

    def history(self, owner):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM reports WHERE owner=? AND state!='deleted' ORDER BY created DESC", (owner,))]

    def maintenance(self):
        """Reclaim expired anonymous files; release jobs abandoned over an hour ago."""
        import shutil
        now = time.time()
        with self.db() as db:
            db.execute("UPDATE reports SET state='failed' WHERE state='processing' AND created<?", (now-3600,))
            expired = db.execute('SELECT id FROM reports WHERE expires<?', (now,)).fetchall()
            for row in expired:
                shutil.rmtree(settings.results_dir / row['id'], ignore_errors=True)
                for ext in settings.allowed_video_extensions:
                    (settings.upload_dir / (row['id'] + ext)).unlink(missing_ok=True)

    def delete(self, task):
        with self.db() as db:
            db.execute("UPDATE reports SET state='deleted' WHERE id=?", (task,))

trial_store = TrialStore()
