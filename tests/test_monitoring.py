"""Local, synthetic-data coverage for the teacher monitoring panel."""

import json
from datetime import datetime, timedelta, timezone

import pytest

import app.monitoring as monitoring
from app.db import get_db
from app.monitoring import bp


@pytest.fixture
def monitor_client(app):
    app.config.update(MONITOR_ALERT_WINDOW_SECONDS=8, MONITOR_ALERT_ERROR_RATE_THRESHOLD=0.01)
    assert "monitoring" in app.blueprints
    return app.test_client()


def _login(client, username="teacher_a"):
    passwords = {"teacher_a": "teacher-test-password", "student_a1": "student-a-test-password",
                 "student_b1": "student-b-test-password"}
    return client.post("/api/login", json={"username": username, "password": passwords[username]})


def _event(db, stamp, *, skill, status=200, class_id=1, event="skill_invocation"):
    db.execute("""INSERT INTO audit_events(timestamp,level,event,request_id,user_id,fields_json)
        VALUES (?, 'INFO', ?, NULL, NULL, ?)""",
        (stamp.isoformat(), event, json.dumps({"class_id": class_id, "skill": skill, "status": status})))


def test_monitoring_requires_teacher_and_validates_window(monitor_client):
    client = monitor_client
    assert client.get("/monitoring").status_code == 401
    assert client.get("/api/monitoring").status_code == 401
    _login(client, "student_a1")
    assert client.get("/monitoring").status_code == 403
    assert client.get("/api/monitoring").status_code == 403
    client.post("/api/logout")
    _login(client)
    assert client.get("/api/monitoring?window=0").status_code == 400
    assert client.get("/api/monitoring?window=300x").status_code == 400
    assert client.get("/monitoring").status_code == 200


def test_empty_state_has_no_invented_skill_or_route_lines(monitor_client):
    _login(monitor_client)
    result = monitor_client.get("/api/monitoring?window=300").json
    assert result["has_skill_data"] is False
    assert result["skills"] == []
    assert result["invocations"]["series"] == []
    assert result["error_rates"] == []
    assert result["http_p95_ms"] is None
    assert result["queue"] == {"pending": 0, "running": 0}
    html = monitor_client.get("/monitoring").get_data(as_text=True)
    assert "当前时间窗没有技能调用记录" in html
    assert "route" not in result


def test_dashboard_uses_actual_skill_labels_and_isolates_class(monitor_client, app, monkeypatch):
    now = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(monitoring, "_now", lambda: now)
    with app.app_context():
        db = get_db()
        for i, skill in enumerate(("数学解题引导", "错题讲解", "教师改分优先")):
            for repeat in range(3):
                _event(db, now - timedelta(minutes=10) + timedelta(minutes=i, seconds=repeat), skill=skill)
        _event(db, now - timedelta(minutes=6), skill="低频技能")
        _event(db, now - timedelta(minutes=2), skill="跨班技能", class_id=2)
        db.execute("""INSERT INTO audit_events(timestamp,level,event,fields_json)
            VALUES (?, 'INFO','http_request',?)""", (now.isoformat(), json.dumps({
                "class_id": 1, "duration_ms": 20, "skill": "数学解题引导",
                "route": "/api/conversations/<id>/messages", "status": 500,
            })))
        _event(db, now, skill="数学解题引导", status=500, event="llm_usage")
        assignment_id = db.execute("INSERT INTO assignments(class_id,title) VALUES (1,'监控测试')").lastrowid
        student_id = db.execute("SELECT id FROM users WHERE username='student_a1'").fetchone()["id"]
        submission_id = db.execute("""INSERT INTO submissions(assignment_id,class_id,user_id,content,content_hash,idempotency_key)
            VALUES (?,1,?,'synthetic','hash','monitor-test')""", (assignment_id, student_id)).lastrowid
        db.execute("INSERT INTO grading_tasks(id,submission_id,class_id,user_id,max_attempts,status) VALUES ('pending-one',?,1,?,3,'pending')", (submission_id, student_id))
        db.commit()
    _login(monitor_client)
    result = monitor_client.get("/api/monitoring?window=3600").json
    assert result["skills"] == ["教师改分优先", "数学解题引导", "错题讲解"]
    assert all("/" not in item for item in result["skills"])
    assert sum(sum(s["values"]) for s in result["invocations"]["series"]) == 9
    assert result["http_p95_ms"] == 20
    assert result["queue"]["pending"] == 1
    assert {item["skill"]: (item["calls"], item["errors"]) for item in result["error_rates"]} == {
        "数学解题引导": (3, 0), "错题讲解": (3, 0), "教师改分优先": (3, 0),
    }


def test_alert_requires_continuous_observation_and_deduplicates(monitor_client, app, monkeypatch):
    clock = [datetime(2026, 11, 16, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(monitoring, "_now", lambda: clock[0])
    with app.app_context():
        db = get_db()
        for i in range(11):
            stamp = clock[0] - timedelta(seconds=8 - i * 0.8)
            _event(db, stamp, skill="数学解题引导", status=500 if i == 0 else 200)
        db.commit()
    _login(monitor_client)

    first = monitor_client.get("/api/monitoring?window=300").json
    assert first["alerts"][0]["status"] == "pending"
    assert first["alerts"][0]["start_at"] == clock[0].isoformat()
    for _ in range(3):
        clock[0] += timedelta(seconds=2)
        with app.app_context():
            _event(get_db(), clock[0], skill="数学解题引导", status=500)
            get_db().commit()
        observed = monitor_client.get("/api/monitoring?window=300").json
        assert observed["alerts"][0]["status"] == "pending"
    clock[0] += timedelta(seconds=2)
    with app.app_context():
        _event(get_db(), clock[0], skill="数学解题引导", status=500)
        get_db().commit()
    triggered = monitor_client.get("/api/monitoring?window=300").json
    assert triggered["alerts"][0]["status"] == "active"
    assert triggered["alerts"][0]["start_at"] == first["alerts"][0]["start_at"]
    assert len(triggered["alerts"]) == 1
    clock[0] += timedelta(seconds=2)
    again = monitor_client.get("/api/monitoring?window=300").json
    assert sum(a["status"] == "active" for a in again["alerts"]) == 1


def test_observation_gap_restarts_alert_duration(monitor_client, app, monkeypatch):
    clock = [datetime(2026, 11, 16, 12, tzinfo=timezone.utc)]
    monkeypatch.setattr(monitoring, "_now", lambda: clock[0])
    with app.app_context():
        _event(get_db(), clock[0], skill="错题讲解", status=500)
        get_db().commit()
    _login(monitor_client)
    assert monitor_client.get("/api/monitoring").json["alerts"][0]["status"] == "pending"
    clock[0] += timedelta(seconds=9)
    with app.app_context():
        _event(get_db(), clock[0], skill="错题讲解", status=500)
        get_db().commit()
    assert monitor_client.get("/api/monitoring").json["alerts"][0]["status"] == "pending"
    with app.app_context():
        alert = get_db().execute("SELECT start_at,status FROM monitor_alerts WHERE skill='错题讲解' AND status='pending'").fetchone()
    assert alert["start_at"] == clock[0].isoformat()
    assert alert["status"] == "pending"


def test_monitoring_openapi_schema_uses_openapi_30_nullable(app):
    assert "monitoring" in app.blueprints
    from app.openapi import build_openapi_document
    schema = build_openapi_document(app)["paths"]["/api/monitoring"]["get"]
    assert schema["parameters"][0]["name"] == "window"
    assert schema["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["http_p95_ms"] == {"type": "number", "nullable": True}
    assert schema["responses"]["401"]["description"]
