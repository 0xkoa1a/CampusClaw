import importlib.util
import math
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "mcp-server" / "app.py"
SPEC = importlib.util.spec_from_file_location("campusclaw_mcp_server", MODULE_PATH)
MCP_SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MCP_SERVER)


@pytest.fixture
def mcp_client(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "test-mcp-token")
    return MCP_SERVER.create_app().test_client()


def rpc(client, method, params=None, request_id=1, token="test-mcp-token"):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.post("/mcp", json={
        "jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {},
    }, headers=headers)


def test_health_and_bearer_authentication(mcp_client):
    assert mcp_client.get("/health").json == {"status": "ok"}
    assert rpc(mcp_client, "tools/list", token=None).status_code == 401
    assert rpc(mcp_client, "tools/list", token="wrong").status_code == 401
    assert rpc(mcp_client, "tools/list").status_code == 200


def test_initialize_and_list_expose_two_tool_schemas(mcp_client):
    initialized = rpc(mcp_client, "initialize", {
        "protocolVersion": "2025-06-18", "clientInfo": {"name": "test", "version": "1"},
        "capabilities": {},
    }).json
    assert initialized["result"]["protocolVersion"] == "2025-06-18"
    assert initialized["result"]["capabilities"] == {"tools": {}}

    response = rpc(mcp_client, "tools/list").json
    tools = {tool["name"]: tool for tool in response["result"]["tools"]}
    assert set(tools) == {"calculate", "unit_convert"}
    assert tools["calculate"]["inputSchema"]["required"] == ["operation", "a", "b"]
    assert tools["unit_convert"]["inputSchema"]["required"] == ["value", "from_unit", "to_unit"]
    assert all(tool["inputSchema"]["additionalProperties"] is False for tool in tools.values())


@pytest.mark.parametrize(("arguments", "expected"), [
    ({"operation": "add", "a": 2, "b": 3}, "5"),
    ({"operation": "subtract", "a": 8, "b": 3}, "5"),
    ({"operation": "multiply", "a": 2, "b": 3}, "6"),
    ({"operation": "divide", "a": 8, "b": 2}, "4.0"),
])
def test_calculate_returns_mcp_content(mcp_client, arguments, expected):
    response = rpc(mcp_client, "tools/call", {"name": "calculate", "arguments": arguments}).json
    assert response["result"] == {"content": [{"type": "text", "text": expected}], "isError": False}


def test_unit_convert_returns_text_content(mcp_client):
    response = rpc(mcp_client, "tools/call", {
        "name": "unit_convert",
        "arguments": {"value": 150, "from_unit": "cm", "to_unit": "m"},
    }).json
    assert response["result"] == {
        "content": [{"type": "text", "text": "150 cm = 1.5 m"}], "isError": False,
    }


@pytest.mark.parametrize("arguments", [
    {"operation": "divide", "a": 1, "b": 0},
    {"operation": "add", "a": True, "b": 1},
    {"operation": "add", "a": 1_000_000_001, "b": 1},
    {"operation": "add", "a": 1, "b": 2, "extra": 3},
    {"operation": "power", "a": 2, "b": 3},
    {"operation": "multiply", "a": 1_000_000, "b": 1_000_000},
])
def test_invalid_calculation_is_a_tool_error(mcp_client, arguments):
    response = rpc(mcp_client, "tools/call", {"name": "calculate", "arguments": arguments}).json
    assert response["result"]["isError"] is True
    assert response["result"]["content"][0]["type"] == "text"
    assert response["result"]["content"][0]["text"]


@pytest.mark.parametrize("arguments", [
    {"value": 1, "from_unit": "m", "to_unit": "kg"},
    {"value": math.inf, "from_unit": "m", "to_unit": "km"},
    {"value": 1, "from_unit": "m", "to_unit": "parsec"},
    {"value": 1, "from_unit": "m", "to_unit": "cm", "extra": 0},
])
def test_invalid_unit_conversion_is_a_tool_error(arguments):
    result = MCP_SERVER._unit_convert(arguments)
    assert result["isError"] is True


def test_unknown_method_returns_json_rpc_error(mcp_client):
    response = rpc(mcp_client, "resources/list").json
    assert response["error"]["code"] == -32601
    assert response["id"] == 1


def test_unknown_tool_and_invalid_protocol_version_are_rejected(mcp_client):
    tool_response = rpc(mcp_client, "tools/call", {"name": "missing", "arguments": {}}).json
    assert tool_response["result"]["isError"] is True
    init_response = rpc(mcp_client, "initialize", {"protocolVersion": "unknown"}).json
    assert init_response["error"]["code"] == -32602


def test_malformed_json_returns_parse_error_and_auth_token_is_not_echoed(mcp_client):
    response = mcp_client.post(
        "/mcp", data="not-json", content_type="application/json",
        headers={"Authorization": "Bearer test-mcp-token"},
    )
    assert response.status_code == 200
    assert response.json["error"]["code"] == -32700
    assert "test-mcp-token" not in response.get_data(as_text=True)


def test_missing_server_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    response = MCP_SERVER.create_app().test_client().post(
        "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 401


def test_mcp_rejects_browser_origin(mcp_client):
    response = mcp_client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'},
                               headers={'Authorization': 'Bearer test-mcp-token', 'Origin': 'https://untrusted.example'})
    assert response.status_code == 403


def test_mcp_bounds_request_size(mcp_client):
    response = mcp_client.post('/mcp', data='x' * 65537, content_type='application/json',
                               headers={'Authorization': 'Bearer test-mcp-token'})
    assert response.status_code == 413
