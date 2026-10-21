import json

from werkzeug.security import generate_password_hash

from app.db import get_db
from app.gateway import GatewayUnavailable
from conftest import login
from test_conversations import events, setup_agent


def create_same_class_student(app):
    with app.app_context():
        db = get_db()
        with db:
            user_id = db.execute(
                """INSERT INTO users
                   (username,display_name,role,class_id,password_hash)
                   VALUES (?,?,?,?,?)""",
                (
                    "student_a2_trace_test",
                    "A 班另一位学生",
                    "student",
                    1,
                    generate_password_hash("student-a2-trace-test-password"),
                ),
            ).lastrowid
        return user_id


def read_traces(client, conversation_id):
    response = client.get(f"/api/conversations/{conversation_id}/traces")
    assert response.status_code == 200
    return response.json["traces"]


def test_trace_records_actual_stream_request_and_catalog(app, client):
    _, conversation_id = setup_agent(app, client)
    app.config.update(
        CHAT_MODEL="trace-test-model",
        EMBEDDING_API_KEY="trace-test-embedding-secret",
        MCP_AUTH_TOKEN="trace-test-mcp-secret",
    )
    captured_messages = []

    def provider(messages):
        captured_messages.append(messages)
        yield "已记录。"

    app.config["STREAM_PROVIDER"] = provider
    result = events(
        client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "请记录这次调用"},
        )
    )
    assert result[-1][0] == "done"

    traces = read_traces(client, conversation_id)
    assert len(traces) == 1
    assert traces[0]["status"] == "complete"
    request_event = next(
        event for event in traces[0]["events"] if event["kind"] == "llm_request"
    )
    body = request_event["payload"]["body"]
    assert body == {
        "model": "trace-test-model",
        "messages": captured_messages[0],
        "stream": True,
        "temperature": 0.2,
        "max_tokens": 450,
    }
    assert any(
        message["role"] == "user" and "请记录这次调用" in message["content"]
        for message in body["messages"]
    )

    serialized = json.dumps(traces, ensure_ascii=False)
    assert "Authorization" not in serialized
    assert "trace-test-embedding-secret" not in serialized
    assert "trace-test-mcp-secret" not in serialized

    catalog_response = client.get("/api/platform/catalog")
    assert catalog_response.status_code == 200
    catalog = catalog_response.json
    assert len(catalog["prompt_templates"]) >= 2
    assert len(catalog["skills"]) >= 2


def test_trace_is_owner_only_within_and_across_classes_and_cascades_on_delete(
    app, client
):
    _, conversation_id = setup_agent(app, client)
    app.config["STREAM_PROVIDER"] = lambda _messages: iter(["仅会话所有者可见。"])
    assert events(
        client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "创建一条调用记录"},
        )
    )[-1][0] == "done"
    assert len(read_traces(client, conversation_id)) == 1

    create_same_class_student(app)
    client.post("/api/logout")
    assert login(client, "student_a2_trace_test", "student-a2-trace-test-password").status_code == 200
    assert client.get(f"/api/conversations/{conversation_id}/traces").status_code == 404

    client.post("/api/logout")
    assert login(client, "student_b1", "student-b-test-password").status_code == 200
    assert client.get(f"/api/conversations/{conversation_id}/traces").status_code == 404

    client.post("/api/logout")
    assert login(client, "student_a1", "student-a-test-password").status_code == 200
    assert len(read_traces(client, conversation_id)) == 1
    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    with app.app_context():
        assert (
            get_db()
            .execute(
                "SELECT COUNT(*) FROM call_traces WHERE conversation_id=?",
                (conversation_id,),
            )
            .fetchone()[0]
            == 0
        )
    assert client.get(f"/api/conversations/{conversation_id}/traces").status_code == 404


def test_failed_stream_persists_partial_message_and_error_trace(app, client):
    _, conversation_id = setup_agent(app, client)

    def failing_provider(_messages):
        yield "已生成的部分回答"
        raise GatewayUnavailable("simulated provider failure")

    app.config["STREAM_PROVIDER"] = failing_provider
    result = events(
        client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "触发部分失败"},
        )
    )
    assert result[-1][0] == "error"

    detail = client.get(f"/api/conversations/{conversation_id}").json
    assistant = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert assistant[-1]["status"] == "partial"
    assert assistant[-1]["content"] == "已生成的部分回答"

    traces = read_traces(client, conversation_id)
    assert len(traces) == 1
    assert traces[0]["status"] == "error"
    assert any(event["kind"] == "llm_request" for event in traces[0]["events"])
    assert any(
        event["kind"] == "llm_test_delta"
        and event["payload"] == "已生成的部分回答"
        for event in traces[0]["events"]
    )
