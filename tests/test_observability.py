import json
import logging
from io import BytesIO

from app.observability import SafeJsonFormatter, bp, init_observability, log_model_usage
from app.openapi import build_openapi_document


def observed_app(app):
    init_observability(app)
    if "audit_events" not in app.blueprints:
        app.register_blueprint(bp)
    return app


def test_init_is_idempotent_and_migrates_seven_column_audit_table(app):
    observed_app(app)
    init_observability(app)
    with app.app_context():
        from app.db import get_db
        columns = [row["name"] for row in get_db().execute("PRAGMA table_info(audit_events)")]
        count = get_db().execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert columns == ["id", "timestamp", "level", "event", "request_id", "user_id", "fields_json"]
    assert count == 0
    assert "/api/audit-events" in build_openapi_document(app)["paths"]


def test_http_request_correlation_auth_fields_audit_api_and_redaction(app, client, capsys):
    observed_app(app)
    response = client.post(
        "/api/login?access_token=query-secret",
        json={"username": "teacher_a", "password": "teacher-test-password"},
    )
    assert response.status_code == 200
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 36
    identity = client.get("/api/me?credential=query-secret")
    assert identity.headers["X-Request-ID"] != request_id

    audit = client.get("/api/audit-events?limit=20")
    assert audit.status_code == 200
    rows = audit.json["audit_events"]
    me_event = next(row for row in rows if row["event"] == "http_request" and row["fields"]["route"] == "/api/me")
    assert me_event["user_id"] == identity.json["id"]
    assert me_event["request_id"] == identity.headers["X-Request-ID"]
    assert me_event["fields"]["status"] == 200
    assert me_event["fields"]["duration_ms"] >= 0
    assert me_event["fields"]["operation"] == "GET"
    assert me_event["fields"]["object"] == "/api/me"
    assert me_event["fields"]["skill"] is None
    assert me_event["fields"]["usage"] is None
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "teacher-test-password" not in output
    assert "query-secret" not in output
    assert "credential=" not in output


def test_audit_api_enforces_teacher_class_scope_and_validates_filters(app, client):
    observed_app(app)
    assert client.get("/api/audit-events").status_code == 401
    client.post("/api/login", json={"username": "student_a1", "password": "student-a-test-password"})
    assert client.get("/api/audit-events").status_code == 403
    client.post("/api/logout")
    client.post("/api/login", json={"username": "teacher_a", "password": "teacher-test-password"})
    assert client.get("/api/audit-events?limit=0").status_code == 400
    assert client.get("/api/audit-events?user_id=0").status_code == 400
    assert client.get("/api/audit-events?from=not-a-date").status_code == 400
    assert client.get("/api/audit-events?from=2026-01-02T00:00:00Z&to=2026-01-01T00:00:00Z").status_code == 400
    assert client.get("/api/audit-events?limit=1").status_code == 200


def test_unknown_model_usage_persists_null_without_request_context(app, capsys):
    observed_app(app)
    with app.app_context():
        assert log_model_usage({"prompt_tokens": "secret", "total_tokens": -1}) == {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
        from app.db import get_db
        row = get_db().execute(
            "SELECT request_id,fields_json FROM audit_events WHERE event='llm_usage' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        fields = json.loads(row["fields_json"])
    assert row["request_id"] is None
    assert fields["usage"] == {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    assert fields["skill"] is None and fields["operation"] is None and fields["object"] is None
    serialized = capsys.readouterr().err
    assert "secret" not in serialized
    assert '"request_id":null' in serialized
    assert '"prompt_tokens":null' in serialized


def test_gateway_and_stream_usage_keep_actual_counts_and_discard_payload(app, monkeypatch, capsys):
    observed_app(app)
    app.config.update(EMBEDDING_BASE_URL="https://gateway.invalid", EMBEDDING_API_KEY="gateway-secret", AI_TIMEOUT_SECONDS=5)

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        "app.gateway.urlopen",
        lambda *_args, **_kwargs: Response(json.dumps({
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18, "private": "discard-me"},
            "choices": [{"message": {"content": "response-body-secret"}}],
        }).encode()),
    )
    from flask import g
    from app.gateway import _post
    with app.test_request_context("/api/conversations/1/messages"):
        g.request_id = "request-from-server"
        g.user = {"id": 5, "username": "student-a", "role": "student", "class_id": 1}
        g.skill_name = "代数指导"
        _post("/chat/completions", {"messages": [{"content": "request-body-secret"}]})
        from app.call_trace import record
        record("llm_sse_data", json.dumps({
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            "choices": [{"delta": {"content": "stream-body-secret"}}],
        }))
    with app.app_context():
        from app.db import get_db
        rows = get_db().execute(
            "SELECT event,request_id,user_id,fields_json FROM audit_events WHERE event IN ('llm_usage','llm_stream_usage') ORDER BY id"
        ).fetchall()
    assert [row["event"] for row in rows] == ["llm_usage", "llm_stream_usage"]
    http_usage = json.loads(rows[0]["fields_json"])
    assert rows[0]["request_id"] == "request-from-server" and rows[0]["user_id"] == 5
    assert http_usage["class_id"] == 1 and http_usage["skill"] == "代数指导"
    assert http_usage["usage"] == {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
    stream_usage = json.loads(rows[1]["fields_json"])
    assert stream_usage["usage"] == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}
    serialized = capsys.readouterr().err
    for secret in ("gateway-secret", "request-body-secret", "response-body-secret", "stream-body-secret", "discard-me"):
        assert secret not in serialized


def test_formatter_does_not_render_other_logger_message_or_exception():
    record = logging.LogRecord("third.party", logging.ERROR, "x.py", 1, "token=%s", ("super-secret",), None)
    record.event = "safe_error"
    rendered = SafeJsonFormatter().format(record)
    assert "super-secret" not in rendered
    assert "token=" not in rendered
    assert json.loads(rendered)["event"] == "safe_error"
