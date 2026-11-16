"""Transactional submissions, outbox versions and leased grading results."""

import hashlib
import time
import uuid

from .agent_store import ApiProblem
from .db import get_db

TERMINAL = {'succeeded', 'failed', 'dead'}


def migrate_tasks(db):
    columns = {r['name'] for r in db.execute('PRAGMA table_info(assignments)')}
    with db:
        db.execute('BEGIN IMMEDIATE')
        for name, definition in {
            'teacher_id': 'INTEGER', 'question': "TEXT NOT NULL DEFAULT ''",
            'reference_answer': "TEXT NOT NULL DEFAULT ''", 'rubric': "TEXT NOT NULL DEFAULT ''",
            'max_score': 'INTEGER NOT NULL DEFAULT 100', 'skill_id': 'INTEGER',
            'created_at': "TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in columns: db.execute(f'ALTER TABLE assignments ADD COLUMN {name} {definition}')
        statements = [
            """CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY, assignment_id INTEGER NOT NULL REFERENCES assignments(id),
                class_id INTEGER NOT NULL REFERENCES classes(id), user_id INTEGER NOT NULL REFERENCES users(id),
                content TEXT NOT NULL, content_hash TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id,assignment_id,idempotency_key))""",
            """CREATE TABLE IF NOT EXISTS grading_tasks (
                id TEXT PRIMARY KEY, submission_id INTEGER NOT NULL UNIQUE REFERENCES submissions(id),
                class_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','succeeded','failed','dead')),
                attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
                next_attempt_at REAL NOT NULL DEFAULT 0, lease_until REAL, lease_token TEXT,
                error TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT, finished_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS grading_results (
                id INTEGER PRIMARY KEY, submission_id INTEGER NOT NULL UNIQUE REFERENCES submissions(id),
                task_id TEXT NOT NULL UNIQUE REFERENCES grading_tasks(id), score REAL NOT NULL,
                feedback TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS task_outbox (
                task_id TEXT PRIMARY KEY REFERENCES grading_tasks(id), generation INTEGER NOT NULL DEFAULT 0,
                kind TEXT NOT NULL DEFAULT 'task', published INTEGER NOT NULL DEFAULT 0,
                available_at REAL NOT NULL DEFAULT 0, published_at REAL)""",
            'CREATE INDEX IF NOT EXISTS idx_tasks_owner ON grading_tasks(class_id,user_id,created_at)',
            'CREATE INDEX IF NOT EXISTS idx_tasks_class_created ON grading_tasks(class_id,created_at DESC,id DESC)',
            'CREATE INDEX IF NOT EXISTS idx_tasks_recovery ON grading_tasks(status,lease_until)',
        ]
        for statement in statements: db.execute(statement)


def accept_submission(assignment_id, class_id, user_id, content, key, max_attempts):
    db = get_db()
    digest = hashlib.sha256(content.encode()).hexdigest()
    with db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('''SELECT t.id,t.status,s.id AS submission_id,s.content_hash FROM submissions s
            JOIN grading_tasks t ON t.submission_id=s.id
            WHERE s.assignment_id=? AND s.user_id=? AND s.idempotency_key=?''', (assignment_id, user_id, key)).fetchone()
        if existing:
            if existing['content_hash'] != digest: raise ApiProblem('同一幂等键不能用于不同正文', 409)
            return {'task_id': existing['id'], 'status': existing['status'], 'submission_id': existing['submission_id'], 'replayed': True}
        sid = db.execute('''INSERT INTO submissions(assignment_id,class_id,user_id,content,content_hash,idempotency_key)
            VALUES (?,?,?,?,?,?)''', (assignment_id, class_id, user_id, content, digest, key)).lastrowid
        task_id = str(uuid.uuid4())
        db.execute('INSERT INTO grading_tasks(id,submission_id,class_id,user_id,max_attempts) VALUES (?,?,?,?,?)',
                   (task_id, sid, class_id, user_id, max_attempts))
        db.execute('INSERT INTO task_outbox(task_id) VALUES (?)', (task_id,))
    return {'task_id': task_id, 'status': 'pending', 'submission_id': sid, 'replayed': False}


def task_json(row):
    result = {key: row[key] for key in ('id', 'submission_id', 'assignment_id', 'assignment_title', 'user_id',
              'content', 'status', 'attempts', 'error', 'created_at', 'started_at', 'finished_at')}
    result['result'] = None if row['score'] is None else {key: row[key] for key in ('score', 'feedback', 'source')}
    return result


TASK_QUERY = '''SELECT t.*,s.assignment_id,s.content,a.title AS assignment_title,r.score,r.feedback,r.source
    FROM grading_tasks t JOIN submissions s ON s.id=t.submission_id
    JOIN assignments a ON a.id=s.assignment_id LEFT JOIN grading_results r ON r.task_id=t.id'''


def schedule(db, task_id, when, kind='task'):
    db.execute('''INSERT INTO task_outbox(task_id,available_at,kind) VALUES (?,?,?)
        ON CONFLICT(task_id) DO UPDATE SET generation=generation+1,published=0,published_at=NULL,
        available_at=excluded.available_at,kind=excluded.kind''', (task_id, when, kind))


def recover_expired(db, now=None):
    now = time.time() if now is None else now
    with db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute("SELECT id,attempts,max_attempts FROM grading_tasks WHERE status='running' AND lease_until<=?", (now,)).fetchall()
        for row in rows:
            dead = row['attempts'] >= row['max_attempts']
            db.execute('''UPDATE grading_tasks SET status=?,lease_until=NULL,lease_token=NULL,error=?,next_attempt_at=?,
                finished_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=?''',
                ('dead' if dead else 'pending', '消费者租约过期', now, dead, row['id']))
            schedule(db, row['id'], now, 'dead' if dead else 'task')
    return len(rows)


def claim_task(db, task_id, lease_seconds, now=None):
    now = time.time() if now is None else now
    token = uuid.uuid4().hex
    with db:
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('''UPDATE grading_tasks SET status='running',attempts=attempts+1,
            started_at=CURRENT_TIMESTAMP,finished_at=NULL,lease_until=?,lease_token=?,error=NULL
            WHERE id=? AND status='pending' AND next_attempt_at<=? AND attempts<max_attempts''',
            (now + lease_seconds, token, task_id, now)).rowcount
        if not changed: return None
        row = db.execute('SELECT * FROM grading_tasks WHERE id=?', (task_id,)).fetchone()
    return dict(row)


def finish_task(db, task, result):
    with db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT id FROM grading_tasks WHERE id=? AND status='running' AND lease_token=?",
                         (task['id'], task['lease_token'])).fetchone()
        if not row: return False
        db.execute('''INSERT INTO grading_results(submission_id,task_id,score,feedback,source) VALUES (?,?,?,?,?)''',
                   (task['submission_id'], task['id'], result['score'], result['feedback'], result['source']))
        db.execute("UPDATE grading_tasks SET status='succeeded',finished_at=CURRENT_TIMESTAMP,lease_until=NULL,lease_token=NULL,error=NULL WHERE id=?", (task['id'],))
    return True


def override_grade(db, task_id, class_id, score, feedback):
    """Atomically make a teacher's grade authoritative for a class task."""
    with db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('''SELECT t.id,t.submission_id FROM grading_tasks t
            JOIN submissions s ON s.id=t.submission_id
            JOIN assignments a ON a.id=s.assignment_id
            WHERE t.id=? AND t.class_id=? AND s.class_id=? AND a.class_id=?''',
            (task_id, class_id, class_id, class_id)).fetchone()
        if row is None:
            return False
        db.execute('''INSERT INTO grading_results(submission_id,task_id,score,feedback,source)
            VALUES (?,?,?,?, 'teacher-override')
            ON CONFLICT(task_id) DO UPDATE SET score=excluded.score,
                feedback=excluded.feedback,source='teacher-override' ''',
            (row['submission_id'], task_id, score, feedback))
        db.execute('''UPDATE grading_tasks SET status='succeeded',finished_at=CURRENT_TIMESTAMP,
            lease_until=NULL,lease_token=NULL,error=NULL WHERE id=? AND class_id=?''',
            (task_id, class_id))
    return True


def fail_task(db, task, reason, transient, delay, now=None):
    now = time.time() if now is None else now
    retry = transient and task['attempts'] < task['max_attempts']
    status = 'pending' if retry else ('dead' if transient else 'failed')
    with db:
        db.execute('BEGIN IMMEDIATE')
        changed = db.execute('''UPDATE grading_tasks SET status=?,error=?,next_attempt_at=?,lease_until=NULL,lease_token=NULL,
            finished_at=CASE WHEN ? THEN NULL ELSE CURRENT_TIMESTAMP END
            WHERE id=? AND status='running' AND lease_token=?''',
            (status, reason[:200], now + delay if retry else now, retry, task['id'], task['lease_token'])).rowcount
        if changed: schedule(db, task['id'], now + delay if retry else now, 'task' if retry else 'dead')
    return bool(changed)
