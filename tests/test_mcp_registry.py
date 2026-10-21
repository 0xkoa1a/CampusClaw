import json
import sys
from types import SimpleNamespace

import pytest

from app.db import connect
from app.mcp_registry import (
    bp,
    migrate_mcp,
    record_tool_call,
    resolve_reference,
    validate_references,
)
from app.openapi import build_openapi_document
from app.agent_store import ApiProblem
from conftest import login


@pytest.fixture
def registry_app(app):
    app.config["MCP_ALLOWED_BASE_URLS"] = ["http://mcp-demo:8090", "http://mcp-alt:8090"]
    if "mcp_registry" not in app.blueprints:
        app.register_blueprint(bp)
    connection = connect(app.config["DATABASE_PATH"])
    try:
        migrate_mcp(connection)
    finally:
        connection.close()
    return app


@pytest.fixture
def registry_client(registry_app):
    return registry_app.test_client()


def create_server(client, *, name="campus-tools", base_url="http://mcp-demo:8090", token_env="MCP_AUTH_TOKEN"):
    return client.post("/api/mcp/servers", json={
        "name": name, "base_url": base_url, "token_env": token_env,
    })


def test_migration_is_idempotent_and_declares_expected_columns(registry_app):
    connection = connect(registry_app.config["DATABASE_PATH"])
    try:
        migrate_mcp(connection)
        servers = {row["name"]: row for row in connection.execute("PRAGMA table_info(mcp_servers)")}
        audit = {row["name"]: row for row in connection.execute("PRAGMA table_info(mcp_audit)")}
        assert set(servers) == {"id", "class_id", "name", "base_url", "token_env", "connected", "tools_json", "last_error"}
        assert servers["token_env"]["dflt_value"] == "'MCP_AUTH_TOKEN'"
        assert servers["connected"]["dflt_value"] == "0"
        assert servers["tools_json"]["dflt_value"] == "'[]'"
        assert servers["last_error"]["dflt_value"] == "''"
        assert set(audit) == {"id", "server_id", "class_id", "user_id", "conversation_id", "round", "tool_ref", "status", "summary", "created_at"}
    finally:
        connection.close()


def test_teacher_server_crud_allowlist_and_secret_is_never_returned(registry_client, registry_app, monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "secret-token-value")
    login(registry_client)

    rejected = create_server(registry_client, base_url="http://127.0.0.1:8080")
    assert rejected.status_code == 400
    rejected_env = create_server(registry_client, name="bad-env", token_env="SECRET_TOKEN")
    assert rejected_env.status_code == 400

    created = create_server(registry_client)
    assert created.status_code == 201
    server = created.json["server"]
    assert server["token_configured"] is True
    assert "token" not in server and "secret-token-value" not in created.get_data(as_text=True)
    assert server["tools"] == [] and server["connected"] is False
    identifier = server["id"]
    assert create_server(registry_client).status_code == 400

    listed = registry_client.get("/api/mcp/servers")
    assert listed.status_code == 200 and len(listed.json["servers"]) == 1
    assert registry_client.put(f"/api/mcp/servers/{identifier}", json={"base_url": "http://mcp-alt:8090"}).status_code == 200


def test_student_forbidden_and_cross_class_server_is_404(registry_client, registry_app):
    login(registry_client)
    created = create_server(registry_client)
    own_id = created.json["server"]["id"]
    connection = connect(registry_app.config["DATABASE_PATH"])
    try:
        with connection:
            other_id = connection.execute(
                "INSERT INTO mcp_servers(class_id,name,base_url) VALUES (2,?,?)",
                ("other-tools", "http://mcp-demo:8090"),
            ).lastrowid
    finally:
        connection.close()

    assert registry_client.get(f"/api/mcp/servers/{other_id}/tools").status_code == 404
    login(registry_client, "student_a1", "student-a-test-password")
    assert registry_client.get("/api/mcp/servers").status_code == 403
    assert registry_client.post(f"/api/mcp/servers/{own_id}/connect").status_code == 403
    assert registry_client.get("/api/mcp/tool-calls").status_code == 403


def test_connect_replaces_cache_and_disconnect_clears_it(registry_client, monkeypatch):
    login(registry_client)
    identifier = create_server(registry_client).json["server"]["id"]
    discovered = [[{"name": "formula_hint", "description": "first"}, {"name": "unit_convert"}]]

    def fake_discover(base_url, token):
        assert base_url == "http://mcp-demo:8090"
        assert token is None
        return discovered.pop(0)

    from app import mcp_registry
    monkeypatch.setattr(mcp_registry, "_token_for", lambda _server: None)
    monkeypatch.setitem(sys.modules, "app.mcp_client", SimpleNamespace(discover=fake_discover))
    first = registry_client.post(f"/api/mcp/servers/{identifier}/connect")
    assert first.status_code == 200
    assert [tool["name"] for tool in first.json["server"]["tools"]] == ["formula_hint", "unit_convert"]

    discovered.append([{"name": "formula_hint", "description": "updated"}])
    second = registry_client.post(f"/api/mcp/servers/{identifier}/connect")
    assert second.status_code == 200
    assert second.json["server"]["tools"] == [{"name": "formula_hint", "description": "updated"}]
    assert registry_client.get(f"/api/mcp/servers/{identifier}/tools").json["tools"] == second.json["server"]["tools"]

    disconnected = registry_client.post(f"/api/mcp/servers/{identifier}/disconnect")
    assert disconnected.status_code == 200
    assert disconnected.json["server"]["connected"] is False
    assert disconnected.json["server"]["tools"] == []


def test_failed_connection_marks_disconnected_clears_cache_and_redacts_error(registry_client, registry_app, monkeypatch):
    login(registry_client)
    identifier = create_server(registry_client).json["server"]["id"]
    connection = connect(registry_app.config["DATABASE_PATH"])
    try:
        with connection:
            connection.execute("UPDATE mcp_servers SET connected=1,tools_json=? WHERE id=?", (json.dumps([{"name": "stale_tool"}]), identifier))
    finally:
        connection.close()

    from app import mcp_registry
    monkeypatch.setattr(mcp_registry, "_token_for", lambda _server: "highly-secret")
    def fail(_base_url, _token):
        raise RuntimeError("http://mcp-demo:8090 Authorization highly-secret")
    monkeypatch.setitem(sys.modules, "app.mcp_client", SimpleNamespace(discover=fail))

    response = registry_client.post(f"/api/mcp/servers/{identifier}/connect")
    assert response.status_code == 503
    assert "mcp-demo" not in response.get_data(as_text=True)
    assert "highly-secret" not in response.get_data(as_text=True)
    server = registry_client.get("/api/mcp/servers").json["servers"][0]
    assert server["connected"] is False and server["tools"] == []
    assert "highly-secret" not in server["last_error"]


def test_server_update_clears_cache_and_name_bound_ref_is_rejected(registry_client, registry_app):
    login(registry_client)
    identifier = create_server(registry_client).json["server"]["id"]
    connection = connect(registry_app.config["DATABASE_PATH"])
    try:
        with connection:
            connection.execute("UPDATE mcp_servers SET connected=1,tools_json=? WHERE id=?", (json.dumps([{"name": "formula_hint"}]), identifier))
    finally:
        connection.close()
    response = registry_client.put(f"/api/mcp/servers/{identifier}", json={"name": "renamed-tools"})
    assert response.status_code == 200
    assert response.json["server"]["connected"] is False
    assert response.json["server"]["tools"] == []
    with registry_app.app_context():
        with pytest.raises(ApiProblem) as stale_binding:
            validate_references(["formula_hint@renamed-tools"], 1)
        assert stale_binding.value.status == 400
        with pytest.raises(ApiProblem) as disconnected:
            resolve_reference("formula_hint@renamed-tools", 1)
        assert disconnected.value.status == 409


def test_validate_and_resolve_references_use_class_connected_cache(registry_app):
    connection = connect(registry_app.config["DATABASE_PATH"])
    try:
        with connection:
            identifier = connection.execute(
                "INSERT INTO mcp_servers(class_id,name,base_url,connected,tools_json) VALUES (1,?,?,1,?)",
                ("campus-tools", "http://mcp-demo:8090", json.dumps([{"name": "formula_hint", "inputSchema": {"type": "object"}}])),
            ).lastrowid
    finally:
        connection.close()

    with registry_app.app_context():
        assert validate_references(["knowledge_search", "calculator", "formula_hint@campus-tools"], 1) is True
        server, tool = resolve_reference("formula_hint@campus-tools", 1)
        assert server["id"] == identifier and tool["inputSchema"] == {"type": "object"}
        for refs in (["bad-name@campus-tools"], ["missing@campus-tools"], ["formula_hint@other-tools"]):
            with pytest.raises(ApiProblem) as error:
                validate_references(refs, 1)
            assert error.value.status == 400
        with pytest.raises(ApiProblem) as cross_class:
            resolve_reference("formula_hint@campus-tools", 2)
        assert cross_class.value.status == 404


def test_audit_is_class_scoped_and_survives_server_deletion(registry_client, registry_app):
    login(registry_client)
    identifier = create_server(registry_client).json["server"]["id"]
    with registry_app.app_context():
        record_tool_call(server_id=identifier, class_id=1, user_id=1, conversation_id=None,
                         round_number=2, tool_ref="formula_hint@campus-tools", status="ok", summary="result: 42")
    assert len(registry_client.get("/api/mcp/tool-calls").json["tool_calls"]) == 1
    assert registry_client.delete(f"/api/mcp/servers/{identifier}").status_code == 204
    audit = registry_client.get("/api/mcp/tool-calls").json["tool_calls"]
    assert len(audit) == 1 and audit[0]["server_id"] is None and audit[0]["summary"] == "result: 42"


def test_api_doc_covers_every_mcp_management_route(registry_app):
    paths = build_openapi_document(registry_app)["paths"]
    assert set(paths["/api/mcp/servers"]) == {"get", "post"}
    assert set(paths["/api/mcp/servers/{identifier}"]) == {"put", "delete"}
    assert {"post"} == set(paths["/api/mcp/servers/{identifier}/connect"])
    assert {"post"} == set(paths["/api/mcp/servers/{identifier}/disconnect"])
    assert {"get"} == set(paths["/api/mcp/servers/{identifier}/tools"])
    assert {"get"} == set(paths["/api/mcp/tool-calls"])
