"""Teacher grade override authorization, validation, and late-provider races."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from werkzeug.security import generate_password_hash

from app import task_store, worker
from app.db import connect
from conftest import login


def _assignment(teacher):
    response = teacher.post("/api/assignments", json={
        "title": "教师改分测试", "question": "简答题", "max_score": 10,
    })
    assert response.status_code == 201
    return response.json["assignment"]


def _submission(student, assignment_id):
    response = student.post(
        f"/api/assignments/{assignment_id}/submissions", json={"content": "答案"},
        headers={"Idempotency-Key": "teacher-override"},
    )
    assert response.status_code == 202
    return response.json["task_id"]


def test_teacher_override_wins_when_provider_returns_late(app):
    teacher = app.test_client()
    student = app.test_client()
    assert login(teacher).status_code == 200
    assert login(student, "student_a1", "student-a-test-password").status_code == 200
    task_id = _submission(student, _assignment(teacher)["id"])
    provider_started, provider_release = Event(), Event()

    def provider(_context):
        provider_started.set()
        assert provider_release.wait(5)
        return {"score": 2, "feedback": "模型较早评分"}

    app.config["GRADING_PROVIDER"] = provider
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(worker.process_task, app, task_id)
        assert provider_started.wait(5)
        response = teacher.put(f"/api/tasks/{task_id}/grade", json={
            "score": 9.5, "feedback": "教师复核后调整",
        })
        assert response.status_code == 200, response.get_data(as_text=True)
        assert response.json["task"]["status"] == "succeeded"
        assert response.json["task"]["result"] == {
            "score": 9.5, "feedback": "教师复核后调整", "source": "teacher-override",
        }
        provider_release.set()
        assert pending.result(timeout=5) == "lease-lost"

    db = connect(app.config["DATABASE_PATH"])
    try:
        task = db.execute("SELECT status,lease_until,lease_token FROM grading_tasks WHERE id=?", (task_id,)).fetchone()
        result = db.execute("SELECT score,feedback,source FROM grading_results WHERE task_id=?", (task_id,)).fetchall()
        assert tuple(task) == ("succeeded", None, None)
        assert len(result) == 1
        assert tuple(result[0]) == (9.5, "教师复核后调整", "teacher-override")
    finally:
        db.close()


def test_student_is_forbidden_and_other_class_task_is_hidden(app):
    teacher_a, student_a, teacher_b = (app.test_client() for _ in range(3))
    assert login(teacher_a).status_code == 200
    assert login(student_a, "student_a1", "student-a-test-password").status_code == 200
    own_task = _submission(student_a, _assignment(teacher_a)["id"])
    assert student_a.put(f"/api/tasks/{own_task}/grade", json={"score": 1, "feedback": "改分"}).status_code == 403

    db = connect(app.config["DATABASE_PATH"])
    try:
        db.execute("INSERT INTO users(username,display_name,role,class_id,password_hash) VALUES (?,?,?,?,?)",
                   ("teacher_b", "B 班教师", "teacher", 2, generate_password_hash("teacher-b-password")))
        db.commit()
    finally:
        db.close()
    assert login(teacher_b, "teacher_b", "teacher-b-password").status_code == 200
    student_b = app.test_client()
    assert login(student_b, "student_b1", "student-b-test-password").status_code == 200
    foreign_task = _submission(student_b, _assignment(teacher_b)["id"])
    assert teacher_a.put(f"/api/tasks/{foreign_task}/grade", json={"score": 1, "feedback": "改分"}).status_code == 404


@pytest.mark.parametrize("payload", [
    {"score": -0.01, "feedback": "反馈"},
    {"score": 10.01, "feedback": "反馈"},
    {"score": float("nan"), "feedback": "反馈"},
    {"score": float("inf"), "feedback": "反馈"},
    {"score": True, "feedback": "反馈"},
    {"score": 5, "feedback": "  "},
    {"score": 5, "feedback": "字" * 2001},
    {"score": "5", "feedback": "反馈"},
])
def test_invalid_override_is_rejected_without_writing_result(app, payload):
    teacher, student = app.test_client(), app.test_client()
    assert login(teacher).status_code == 200
    assert login(student, "student_a1", "student-a-test-password").status_code == 200
    task_id = _submission(student, _assignment(teacher)["id"])

    response = teacher.put(f"/api/tasks/{task_id}/grade", json=payload)
    assert response.status_code == 400
    db = connect(app.config["DATABASE_PATH"])
    try:
        assert db.execute("SELECT COUNT(*) FROM grading_results WHERE task_id=?", (task_id,)).fetchone()[0] == 0
        assert db.execute("SELECT status FROM grading_tasks WHERE id=?", (task_id,)).fetchone()[0] == "pending"
    finally:
        db.close()
