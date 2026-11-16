"""Independent grading consumer with leased commits and a transactional outbox."""
import json
import logging
import random
import signal
import threading
import time

from .db import connect, get_db
from .task_queue import BrokerUnavailable, RabbitBroker, dispatch_pending
from .task_store import claim_task, fail_task, finish_task


def submission_context(db, task):
    from .grading import PermanentGradingError
    row = db.execute('''SELECT s.content,s.class_id,s.user_id,a.class_id AS assignment_class,
        a.title,a.question,a.reference_answer,a.rubric,a.max_score,a.skill_id,
        u.class_id AS user_class,u.role AS user_role FROM submissions s
        JOIN assignments a ON a.id=s.assignment_id JOIN users u ON u.id=s.user_id WHERE s.id=?''',
        (task['submission_id'],)).fetchone()
    if row is None or row['class_id'] != task['class_id'] or row['assignment_class'] != task['class_id'] or row['user_class'] != task['class_id'] or row['user_role'] != 'student':
        raise PermanentGradingError('提交的归属或身份已失效')
    context = {key: row[key] for key in ('title', 'question', 'reference_answer', 'rubric', 'max_score', 'content')}
    context['skill_description'] = ''
    if row['skill_id'] is not None:
        skill = db.execute('SELECT description,enabled FROM skills WHERE id=? AND class_id=?', (row['skill_id'], task['class_id'])).fetchone()
        if skill is None or not skill['enabled']: raise PermanentGradingError('批改技能已停用或不存在')
        context['skill_description'] = skill['description']
    return context


def process_task(app, task_id):
    from .grading import PermanentGradingError, TransientGradingError, grade_submission
    with app.app_context():
        db = get_db()
        task = claim_task(db, task_id, app.config['TASK_LEASE_SECONDS'])
        if task is None: return 'duplicate-or-not-due'
        from .observability import _emit, execution_context
        audit_scope = {'request_id':f'task:{task_id}', 'user_id':task['user_id'],
            'class_id':task['class_id'], 'skill':'assignment_grading'}
        token = execution_context.set(audit_scope)
        started = time.monotonic()
        try:
            try:
                result = grade_submission(submission_context(db, task))
            finally:
                execution_context.reset(token)
        except (PermanentGradingError, TransientGradingError) as exc:
            temporary = isinstance(exc, TransientGradingError)
            base = app.config['TASK_RETRY_BASE_SECONDS']
            delay = min(300, base * 2 ** (task['attempts'] - 1) + random.uniform(0, base))
            saved = fail_task(db, task, str(exc), temporary, delay)
            outcome = ('retry' if temporary and task['attempts'] < task['max_attempts'] else ('dead' if temporary else 'failed')) if saved else 'lease-lost'
        else:
            outcome = 'succeeded' if finish_task(db, task, result) else 'lease-lost'
        _emit('skill_invocation', **audit_scope, operation='grading', object=f'task:{task_id}',
              status=200 if outcome=='succeeded' else 503,
              duration_ms=round((time.monotonic()-started)*1000,3), usage=None)
        return outcome


def serve(app, stop=None, broker_factory=None):
    stop = stop or threading.Event()
    factory = broker_factory or (lambda: RabbitBroker(app.config['RABBITMQ_URL'], app.config['TASK_QUEUE_NAME']))

    def dispatch_loop():
        db, broker = connect(app.config['DATABASE_PATH']), factory()
        try:
            while not stop.is_set():
                try:
                    dispatch_pending(db, broker)
                except Exception as exc:
                    app.logger.warning('outbox retry pending: %s', type(exc).__name__)
                    stop.wait(1)
                stop.wait(.25)
        finally:
            broker.close()
            db.close()

    dispatcher = threading.Thread(target=dispatch_loop, name='grading-outbox', daemon=True)
    dispatcher.start()
    broker = factory()
    try:
        while not stop.is_set():
            try:
                if not broker.consume_once(lambda identifier: process_task(app, identifier)): stop.wait(.2)
            except BrokerUnavailable:
                app.logger.warning('consumer reconnect pending')
                stop.wait(1)
    finally:
        broker.close()
        stop.set()
        dispatcher.join(timeout=10)


def main():
    from . import create_app
    app, stop = create_app(), threading.Event()
    app.logger.setLevel(logging.INFO)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    serve(app, stop)


if __name__ == '__main__': main()
