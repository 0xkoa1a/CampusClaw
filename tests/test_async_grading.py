"""Async grading regression tests; FakeBroker does not verify real RabbitMQ semantics."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug.security import generate_password_hash

from app import db as db_module
from app import grading, task_queue, task_store, worker
from app.db import connect
from conftest import login


def _new_assignment(client):
    response = client.post("/api/assignments", json={
        "title": "异步批改题", "question": "1+1=?", "reference_answer": "2",
        "rubric": "答案正确得满分", "max_score": 10,
    })
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.json["assignment"]


def _submit(client, assignment_id, content="2", key="attempt-1"):
    return client.post(
        f"/api/assignments/{assignment_id}/submissions",
        json={"content": content}, headers={"Idempotency-Key": key},
    )


def _counts(app):
    db = connect(app.config["DATABASE_PATH"])
    try:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("submissions", "grading_tasks", "task_outbox")
        }
    finally:
        db.close()
def _student_client(app, username="student_a1", password="student-a-test-password"):
    client = app.test_client()
    assert login(client, username, password).status_code == 200
    return client


def _accepted_submission(app, teacher_client, student_client, content="2", key="attempt-1"):
    assignment = _new_assignment(teacher_client)
    response = _submit(student_client, assignment["id"], content, key)
    assert response.status_code == 202, response.get_data(as_text=True)
    return assignment, response.json


def test_submission_is_accepted_without_calling_provider(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    assignment = _new_assignment(teacher)
    student = _student_client(app)
    calls = []
    app.config["GRADING_PROVIDER"] = lambda _ctx: calls.append(_ctx)
    response = _submit(student, assignment["id"])
    assert response.status_code == 202
    assert response.json["status"] == "pending"
    assert student.get(f"/api/tasks/{response.json['task_id']}").status_code == 200
    assert calls == []
    assert _counts(app) == {"submissions": 1, "grading_tasks": 1, "task_outbox": 1}


def test_task_visibility_and_student_assignment_redaction(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    assignment = _new_assignment(teacher)
    assert "reference_answer" in assignment and "rubric" in assignment
    student = _student_client(app)
    student_assignment = student.get(f"/api/assignments/{assignment['id']}")
    assert student_assignment.status_code == 200
    assert "reference_answer" not in student_assignment.json["assignment"]
    assert "rubric" not in student_assignment.json["assignment"]
    submitted = _submit(student, assignment["id"])
    task_id = submitted.json["task_id"]

    own = student.get(f"/api/tasks/{task_id}")
    assert own.status_code == 200
    assert own.json["task"]["result"] is None
    assert "reference_answer" not in own.get_data(as_text=True)
    assert "rubric" not in own.get_data(as_text=True)
    assert teacher.get(f"/api/tasks/{task_id}").status_code == 200

    foreign = _student_client(app, "student_b1", "student-b-test-password")
    assert foreign.get(f"/api/tasks/{task_id}").status_code == 404
    assert foreign.get("/api/assignments/1").status_code == 404

    db = connect(app.config["DATABASE_PATH"])
    try:
        db.execute("INSERT INTO users(username,display_name,role,class_id,password_hash) VALUES (?,?,?,?,?)",
                   ("student_a2", "同班学生", "student", 1, generate_password_hash("student-a2-password")))
        db.commit()
    finally:
        db.close()
    classmate = _student_client(app, "student_a2", "student-a2-password")
    assert classmate.get(f"/api/tasks/{task_id}").status_code == 404


def test_idempotency_same_content_replays_and_changed_content_conflicts(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    student = _student_client(app)
    assignment, first = _accepted_submission(app, teacher, student)
    replay = _submit(student, assignment["id"], "2", "attempt-1")
    conflict = _submit(student, assignment["id"], "3", "attempt-1")
    assert replay.status_code == 202 and replay.json["task_id"] == first["task_id"]
    assert conflict.status_code == 409
    assert _counts(app) == {"submissions": 1, "grading_tasks": 1, "task_outbox": 1}


def test_concurrent_same_key_creates_one_submission_task_and_outbox(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    assignment = _new_assignment(teacher)

    def submit_once(_):
        client = _student_client(app)
        response = _submit(client, assignment["id"], "same answer", "concurrent-key")
        return response.status_code, response.json

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(submit_once, range(16)))
    assert all(status == 202 for status, _ in outcomes)
    assert len({data["task_id"] for _, data in outcomes}) == 1
    assert _counts(app) == {"submissions": 1, "grading_tasks": 1, "task_outbox": 1}


def test_outbox_insert_failure_rolls_back_acceptance(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    assignment = _new_assignment(teacher)
    student = _student_client(app)
    db = connect(app.config["DATABASE_PATH"])
    try:
        db.execute("""CREATE TRIGGER reject_outbox BEFORE INSERT ON task_outbox
            BEGIN SELECT RAISE(ABORT, 'injected outbox failure'); END""")
        db.commit()
    finally:
        db.close()
    response = _submit(student, assignment["id"])
    assert response.status_code == 503
    assert _counts(app) == {"submissions": 0, "grading_tasks": 0, "task_outbox": 0}


def test_task_migration_is_idempotent_and_preserves_legacy_assignment(app):
    db = connect(app.config["DATABASE_PATH"])
    try:
        legacy_id = db.execute("INSERT INTO assignments(class_id,title) VALUES (1,'旧作业')").lastrowid
        db.commit()
    finally:
        db.close()
    db_module.migrate(app.config["DATABASE_PATH"])
    db_module.migrate(app.config["DATABASE_PATH"])
    db = connect(app.config["DATABASE_PATH"])
    try:
        row = db.execute("SELECT id,title,question,reference_answer,rubric,max_score FROM assignments WHERE id=?",
                         (legacy_id,)).fetchone()
        assert tuple(row) == (legacy_id, "旧作业", "", "", "", 100)
        assert db.execute("SELECT COUNT(*) FROM grading_tasks").fetchone()[0] == 0
    finally:
        db.close()


def test_migrate_tasks_from_standalone_legacy_three_column_schema_twice(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    db = connect(path)
    try:
        db.execute("CREATE TABLE assignments (id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, title TEXT NOT NULL)")
        db.execute("INSERT INTO assignments(id,class_id,title) VALUES (41,7,'历史题目')")
        db.commit()
    finally:
        db.close()

    db = connect(path)
    try:
        task_store.migrate_tasks(db)
        task_store.migrate_tasks(db)
        assignment = db.execute("SELECT id,class_id,title,question,reference_answer,rubric,max_score FROM assignments WHERE id=41").fetchone()
        assert tuple(assignment) == (41, 7, "历史题目", "", "", "", 100)
        assert {row["name"] for row in db.execute("PRAGMA table_info(assignments)")} >= {
            "teacher_id", "question", "reference_answer", "rubric", "max_score", "skill_id", "created_at",
        }
        assert db.execute("SELECT COUNT(*) FROM grading_tasks").fetchone()[0] == 0
    finally:
        db.close()


def test_migrate_tasks_authorizer_failure_rolls_back_prior_alters(tmp_path):
    path = tmp_path / "denied-migration.sqlite3"
    db = connect(path)
    try:
        db.execute("CREATE TABLE assignments (id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL, title TEXT NOT NULL)")
        db.execute("INSERT INTO assignments(id,class_id,title) VALUES (9,2,'保留题目')")
        db.commit()

        def deny_results_table(action, arg1, _arg2, _database, _trigger):
            if action == sqlite3.SQLITE_CREATE_TABLE and arg1 == "grading_results":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(deny_results_table)
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            task_store.migrate_tasks(db)
        db.set_authorizer(None)

        columns = {row["name"] for row in db.execute("PRAGMA table_info(assignments)")}
        assert columns == {"id", "class_id", "title"}
        assert tuple(db.execute("SELECT id,class_id,title FROM assignments").fetchone()) == (9, 2, "保留题目")
        tables = {row["name"] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables == {"assignments"}
    finally:
        db.close()
def test_worker_persists_one_result_and_duplicate_delivery_does_not_regrade(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    student = _student_client(app)
    assignment, accepted = _accepted_submission(app, teacher, student)
    calls = []
    app.config["GRADING_PROVIDER"] = lambda context: (
        calls.append(context) or {"score": 10, "feedback": "正确", "extra": "discard"}
    )
    assert worker.process_task(app, accepted["task_id"]) == "succeeded"
    assert worker.process_task(app, accepted["task_id"]) == "duplicate-or-not-due"
    assert len(calls) == 1
    task_response = student.get(f"/api/tasks/{accepted['task_id']}")
    assert task_response.json["task"]["result"] == {
        "score": 10.0, "feedback": "正确", "source": "test-provider",
    }
    db = connect(app.config["DATABASE_PATH"])
    try:
        assert db.execute("SELECT COUNT(*) FROM grading_results").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO grading_results(submission_id,task_id,score,feedback,source) VALUES (?,?,?,?,?)",
                       (accepted["submission_id"], accepted["task_id"], 1, "duplicate", "test-provider"))
    finally:
        db.close()


def test_transient_retries_then_dead_letters_and_permanent_failure_stops(app, monkeypatch):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    student = _student_client(app)
    _, accepted = _accepted_submission(app, teacher, student)
    monkeypatch.setattr(grading, "grade_submission", lambda _ctx: (_ for _ in ()).throw(
        grading.TransientGradingError("safe retry")))
    for attempt in (1, 2):
        assert worker.process_task(app, accepted["task_id"]) == "retry"
        db = connect(app.config["DATABASE_PATH"])
        try:
            row = db.execute("SELECT status,attempts FROM grading_tasks WHERE id=?", (accepted["task_id"],)).fetchone()
            assert tuple(row) == ("pending", attempt)
            db.execute("UPDATE grading_tasks SET next_attempt_at=0 WHERE id=?", (accepted["task_id"],))
            db.commit()
        finally:
            db.close()
    assert worker.process_task(app, accepted["task_id"]) == "dead"
    db = connect(app.config["DATABASE_PATH"])
    try:
        row = db.execute("SELECT status,attempts,error FROM grading_tasks WHERE id=?", (accepted["task_id"],)).fetchone()
        assert tuple(row) == ("dead", 3, "safe retry")
        outbox = db.execute("SELECT kind,published FROM task_outbox WHERE task_id=?", (accepted["task_id"],)).fetchone()
        assert tuple(outbox) == ("dead", 0)
    finally:
        db.close()

    assignment = _new_assignment(teacher)
    accepted_permanent = _submit(student, assignment["id"], "other", "permanent-key").json
    monkeypatch.setattr(grading, "grade_submission", lambda _ctx: (_ for _ in ()).throw(
        grading.PermanentGradingError("invalid grading input")))
    assert worker.process_task(app, accepted_permanent["task_id"]) == "failed"
    db = connect(app.config["DATABASE_PATH"])
    try:
        row = db.execute("SELECT status,attempts,error FROM grading_tasks WHERE id=?",
                         (accepted_permanent["task_id"],)).fetchone()
        assert tuple(row) == ("failed", 1, "invalid grading input")
    finally:
        db.close()


def test_leases_recover_and_stale_token_cannot_finish(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    student = _student_client(app)
    _, accepted = _accepted_submission(app, teacher, student)
    db = connect(app.config["DATABASE_PATH"])
    try:
        first_claim = task_store.claim_task(db, accepted["task_id"], lease_seconds=5, now=100)
        assert first_claim and first_claim["attempts"] == 1
        assert task_store.claim_task(db, accepted["task_id"], 5, now=101) is None
        assert task_store.recover_expired(db, now=106) == 1
        recovered = db.execute("SELECT status,lease_token FROM grading_tasks WHERE id=?",
                               (accepted["task_id"],)).fetchone()
        assert recovered["status"] == "pending" and recovered["lease_token"] is None
        second_claim = task_store.claim_task(db, accepted["task_id"], 5, now=107)
        assert second_claim and second_claim["lease_token"] != first_claim["lease_token"]
        result = {"score": 5, "feedback": "done", "source": "test-provider"}
        assert task_store.finish_task(db, first_claim, result) is False
        assert task_store.finish_task(db, second_claim, result) is True
        assert db.execute("SELECT status FROM grading_tasks WHERE id=?", (accepted["task_id"],)).fetchone()[0] == "succeeded"
        assert db.execute("SELECT COUNT(*) FROM grading_results WHERE task_id=?", (accepted["task_id"],)).fetchone()[0] == 1
    finally:
        db.close()


class FakeBroker:
    """Application-level broker substitute; provides no RabbitMQ durability evidence."""

    def __init__(self, fail=False, on_publish=None):
        self.fail = fail
        self.on_publish = on_publish
        self.published = []

    def publish(self, task_id, dead=False):
        self.published.append((task_id, dead))
        if self.on_publish:
            self.on_publish(task_id, dead)
        if self.fail:
            raise task_queue.BrokerUnavailable("fake publish failure")


def test_outbox_marks_published_only_after_broker_publish_confirmation(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    student = _student_client(app)
    _, accepted = _accepted_submission(app, teacher, student)
    db = connect(app.config["DATABASE_PATH"])
    try:
        broker = FakeBroker(fail=True)
        with pytest.raises(task_queue.BrokerUnavailable):
            task_queue.dispatch_pending(db, broker, now=200)
        row = db.execute("SELECT published FROM task_outbox WHERE task_id=?", (accepted["task_id"],)).fetchone()
        assert row[0] == 0
        broker = FakeBroker()
        assert task_queue.dispatch_pending(db, broker, now=201) == 1
        row = db.execute("SELECT published,published_at FROM task_outbox WHERE task_id=?",
                         (accepted["task_id"],)).fetchone()
        assert tuple(row) == (1, 201)
        assert broker.published == [(accepted["task_id"], False)]
    finally:
        db.close()


def test_old_publish_confirmation_cannot_mark_new_outbox_generation(app):
    teacher = app.test_client()
    assert login(teacher).status_code == 200
    student = _student_client(app)
    _, accepted = _accepted_submission(app, teacher, student)
    db = connect(app.config["DATABASE_PATH"])
    try:
        def schedule_new_generation(task_id, dead):
            assert not dead
            task_store.schedule(db, task_id, when=300, kind="task")

        broker = FakeBroker(on_publish=schedule_new_generation)
        assert task_queue.dispatch_pending(db, broker, now=200) == 1
        row = db.execute("SELECT generation,published,published_at,available_at FROM task_outbox WHERE task_id=?",
                         (accepted["task_id"],)).fetchone()
        assert tuple(row) == (1, 0, None, 300)
    finally:
        db.close()
