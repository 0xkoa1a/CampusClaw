"""Teacher-managed MCP server registry, discovery cache and call audit."""

import json
import os
import re
import sqlite3

from flask import Blueprint, current_app, g, jsonify, request

from .agent_store import ApiProblem, missing
from .auth import require_user
from .db import get_db
from .openapi import api_doc


bp = Blueprint("mcp_registry", __name__)

_SERVER_NAME = re.compile(r"[a-z][a-z0-9-]*\Z")
_TOOL_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")
_REFERENCE = re.compile(r"([a-z][a-z0-9_]*)@([a-z][a-z0-9-]*)\Z")
_TOKEN_ENV = re.compile(r"MCP_[A-Z0-9_]+\Z")
_BUILTIN_TOOLS = {"knowledge_search", "calculator"}
_DEFAULT_BASE_URLS = ["http://mcp-demo:8090"]

SERVER_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"}, "class_id": {"type": "integer"},
        "name": {"type": "string"}, "base_url": {"type": "string"},
        "token_env": {"type": "string"}, "token_configured": {"type": "boolean"},
        "connected": {"type": "boolean"}, "tools": {"type": "array", "items": {"type": "object"}},
        "last_error": {"type": "string"},
    },
}
SERVER_LIST_SCHEMA = {"type": "object", "properties": {"servers": {"type": "array", "items": SERVER_SCHEMA}}}
SERVER_WRAPPER_SCHEMA = {"type": "object", "properties": {"server": SERVER_SCHEMA}}
TOOLS_SCHEMA = {"type": "object", "properties": {"server_id": {"type": "integer"}, "tools": {"type": "array", "items": {"type": "object"}}}}
AUDIT_SCHEMA = {"type": "object", "properties": {"tool_calls": {"type": "array", "items": {
    "type": "object", "properties": {
        "id": {"type": "integer"}, "server_id": {"type": "integer", "nullable": True},
        "class_id": {"type": "integer"}, "user_id": {"type": "integer"},
        "conversation_id": {"type": "integer", "nullable": True}, "round": {"type": "integer"},
        "tool_ref": {"type": "string"}, "status": {"type": "string"},
        "summary": {"type": "string"}, "created_at": {"type": "string"},
    },
}}}}
OK_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def migrate_mcp(connection):
    """Create MCP registry and audit tables; safe to run repeatedly."""
    with connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS mcp_servers (
            id INTEGER PRIMARY KEY,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            base_url TEXT NOT NULL,
            token_env TEXT NOT NULL DEFAULT 'MCP_AUTH_TOKEN',
            connected INTEGER NOT NULL DEFAULT 0 CHECK(connected IN (0,1)),
            tools_json TEXT NOT NULL DEFAULT '[]',
            last_error TEXT NOT NULL DEFAULT '',
            UNIQUE(class_id,name)
        )""")
        connection.execute("""CREATE TABLE IF NOT EXISTS mcp_audit (
            id INTEGER PRIMARY KEY,
            server_id INTEGER REFERENCES mcp_servers(id) ON DELETE SET NULL,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            conversation_id INTEGER,
            round INTEGER NOT NULL,
            tool_ref TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_mcp_audit_class_created ON mcp_audit(class_id,created_at DESC,id DESC)")


@bp.errorhandler(ApiProblem)
def handle_api_problem(error):
    return jsonify(error=str(error)), error.status


def _permission():
    denied = require_user()
    if denied:
        return denied
    if g.user["role"] != "teacher":
        return jsonify(error="需要教师权限"), 403
    return None


def _server(identifier, class_id=None):
    class_id = g.user["class_id"] if class_id is None else class_id
    row = get_db().execute(
        "SELECT * FROM mcp_servers WHERE id=? AND class_id=?", (identifier, class_id)
    ).fetchone()
    if row is None:
        raise missing()
    return dict(row)


def _allowed_base_urls():
    allowed = current_app.config.get("MCP_ALLOWED_BASE_URLS", _DEFAULT_BASE_URLS)
    return allowed if isinstance(allowed, list) else []


def _validate_base_url(value):
    if not isinstance(value, str) or value not in _allowed_base_urls():
        raise ApiProblem("Base URL 不在允许列表中")
    return value


def _validate_token_env(value):
    if not isinstance(value, str) or not _TOKEN_ENV.fullmatch(value):
        raise ApiProblem("token_env须为MCP_开头的大写环境变量名")
    return value


def _token_for(server):
    key = server["token_env"]
    configured = current_app.config.get(key)
    if configured:
        return configured
    return os.environ.get(key)


def _decode_tools(server):
    try:
        tools = json.loads(server["tools_json"])
    except (TypeError, json.JSONDecodeError):
        return []
    return tools if isinstance(tools, list) else []


def _public_server(server):
    return {
        "id": server["id"], "class_id": server["class_id"], "name": server["name"],
        "base_url": server["base_url"], "token_env": server["token_env"],
        "token_configured": bool(_token_for(server)), "connected": bool(server["connected"]),
        "tools": _decode_tools(server), "last_error": server["last_error"],
    }


def _payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiProblem("需要JSON对象")
    return data


def _validate_server_fields(data, current=None):
    current = current or {}
    name = data.get("name", current.get("name"))
    base_url = data.get("base_url", current.get("base_url"))
    token_env = data.get("token_env", current.get("token_env", "MCP_AUTH_TOKEN"))
    if not isinstance(name, str) or len(name) > 64 or not _SERVER_NAME.fullmatch(name):
        raise ApiProblem("服务器名称须以小写字母开头，且只含小写字母、数字和连字符")
    return name, _validate_base_url(base_url), _validate_token_env(token_env)


def _valid_discovery(tools):
    if not isinstance(tools, list):
        raise ValueError("invalid tools list")
    normalized = []
    names = set()
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("invalid tool entry")
        name = tool.get("name")
        if not isinstance(name, str) or not _TOOL_NAME.fullmatch(name) or name in names:
            raise ValueError("invalid tool name")
        # Ensure the cache is JSON-safe before writing it to SQLite.
        json.dumps(tool, ensure_ascii=False, allow_nan=False)
        names.add(name)
        normalized.append(tool)
    return normalized


def validate_references(refs, class_id):
    """Validate skill tool references against built-ins or this class's live cache."""
    if not isinstance(refs, list):
        raise ApiProblem("工具引用须为数组")
    for ref in refs:
        if not isinstance(ref, str):
            raise ApiProblem("工具引用格式不正确")
        if ref in _BUILTIN_TOOLS:
            continue
        match = _REFERENCE.fullmatch(ref)
        if not match:
            raise ApiProblem(f"工具引用格式不正确：{ref}")
        tool_name, server_name = match.groups()
        row = get_db().execute(
            "SELECT connected,tools_json FROM mcp_servers WHERE class_id=? AND name=?",
            (class_id, server_name),
        ).fetchone()
        if row is None or not row["connected"]:
            raise ApiProblem(f"MCP工具不可用：{ref}")
        if not any(tool.get("name") == tool_name for tool in _decode_tools(row)):
            raise ApiProblem(f"MCP工具未在最近发现清单中：{ref}")
    return True


def resolve_reference(ref, class_id):
    """Resolve a runtime MCP reference and return its server, including its secret token."""
    match = _REFERENCE.fullmatch(ref) if isinstance(ref, str) else None
    if not match:
        raise ApiProblem("MCP工具引用格式不正确")
    tool_name, server_name = match.groups()
    row = get_db().execute(
        "SELECT * FROM mcp_servers WHERE class_id=? AND name=?", (class_id, server_name)
    ).fetchone()
    if row is None:
        raise missing()
    server = dict(row)
    if not server["connected"]:
        raise ApiProblem("MCP服务器未连接", 409)
    tool = next((item for item in _decode_tools(server) if item.get("name") == tool_name), None)
    if tool is None:
        raise missing()
    _validate_base_url(server["base_url"])
    server["token"] = _token_for(server)
    return server, tool


@bp.route("/api/mcp/servers", methods=["GET", "POST"])
@api_doc({
    "get": {"summary": "列出本班MCP服务器", "x-response-schema": SERVER_LIST_SCHEMA, "x-error-statuses": ["403"]},
    "post": {"summary": "登记本班MCP服务器", "x-success-status": 201, "x-response-schema": SERVER_WRAPPER_SCHEMA,
             "x-error-statuses": ["400", "403"], "requestBody": {"required": True, "content": {"application/json": {"schema": {
                 "type": "object", "required": ["name", "base_url"], "properties": {
                     "name": {"type": "string", "pattern": "^[a-z][a-z0-9-]*$"},
                     "base_url": {"type": "string"}, "token_env": {"type": "string", "default": "MCP_AUTH_TOKEN"},
                 },
             }}}}},
})
def servers():
    denied = _permission()
    if denied:
        return denied
    connection = get_db()
    class_id = g.user["class_id"]
    if request.method == "GET":
        rows = connection.execute("SELECT * FROM mcp_servers WHERE class_id=? ORDER BY id", (class_id,)).fetchall()
        return jsonify(servers=[_public_server(dict(row)) for row in rows])
    name, base_url, token_env = _validate_server_fields(_payload())
    try:
        with connection:
            identifier = connection.execute(
                "INSERT INTO mcp_servers(class_id,name,base_url,token_env) VALUES (?,?,?,?)",
                (class_id, name, base_url, token_env),
            ).lastrowid
    except sqlite3.IntegrityError as exc:
        raise ApiProblem("本班已存在同名MCP服务器") from exc
    return jsonify(server=_public_server(_server(identifier))), 201


@bp.route("/api/mcp/servers/<int:identifier>", methods=["PUT", "DELETE"])
@api_doc({
    "put": {"summary": "更新本班MCP服务器", "x-response-schema": SERVER_WRAPPER_SCHEMA,
            "x-error-statuses": ["400", "403", "404"], "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": {"name": {"type": "string"}, "base_url": {"type": "string"}, "token_env": {"type": "string"}},
            }}}}},
    "delete": {"summary": "删除本班MCP服务器并保留审计", "x-error-statuses": ["403", "404"], "responses": {"204": {"description": "已删除，审计记录保留"}}},
})
def server(identifier):
    denied = _permission()
    if denied:
        return denied
    connection = get_db()
    class_id = g.user["class_id"]
    current = _server(identifier, class_id)
    if request.method == "DELETE":
        with connection:
            connection.execute("DELETE FROM mcp_servers WHERE id=? AND class_id=?", (identifier, class_id))
        return "", 204
    name, base_url, token_env = _validate_server_fields(_payload(), current)
    changed = any(current[key] != value for key, value in (("name", name), ("base_url", base_url), ("token_env", token_env)))
    try:
        with connection:
            if changed:
                connection.execute(
                    "UPDATE mcp_servers SET name=?,base_url=?,token_env=?,connected=0,tools_json='[]',last_error='' WHERE id=? AND class_id=?",
                    (name, base_url, token_env, identifier, class_id),
                )
            else:
                connection.execute(
                    "UPDATE mcp_servers SET name=?,base_url=?,token_env=? WHERE id=? AND class_id=?",
                    (name, base_url, token_env, identifier, class_id),
                )
    except sqlite3.IntegrityError as exc:
        raise ApiProblem("本班已存在同名MCP服务器") from exc
    return jsonify(server=_public_server(_server(identifier, class_id)))


@bp.post("/api/mcp/servers/<int:identifier>/connect")
@api_doc({"post": {"summary": "连接MCP服务器并整体替换发现缓存", "x-response-schema": SERVER_WRAPPER_SCHEMA,
                    "x-error-statuses": ["403", "404"]}})
def connect_server(identifier):
    denied = _permission()
    if denied:
        return denied
    server = _server(identifier)
    try:
        _validate_base_url(server["base_url"])
        from .mcp_client import discover
        tools = _valid_discovery(discover(server["base_url"], _token_for(server)))
    except Exception as exc:
        # A failed refresh invalidates stale tools so they cannot be called later.
        connection = get_db()
        with connection:
            connection.execute(
                "UPDATE mcp_servers SET connected=0,tools_json='[]',last_error=? WHERE id=? AND class_id=?",
                ("连接失败，请检查服务器地址、令牌和 MCP 服务状态", identifier, g.user["class_id"]),
            )
        current_app.logger.warning("MCP discovery failed for server id=%s (%s)", identifier, type(exc).__name__)
        return jsonify(error="MCP服务器连接失败，请检查配置和服务状态"), 503
    connection = get_db()
    with connection:
        connection.execute(
            "UPDATE mcp_servers SET connected=1,tools_json=?,last_error='' WHERE id=? AND class_id=?",
            (json.dumps(tools, ensure_ascii=False, allow_nan=False), identifier, g.user["class_id"]),
        )
    return jsonify(server=_public_server(_server(identifier)))


@bp.post("/api/mcp/servers/<int:identifier>/disconnect")
@api_doc({"post": {"summary": "断开MCP服务器并清空发现缓存", "x-response-schema": SERVER_WRAPPER_SCHEMA,
                    "x-error-statuses": ["403", "404"]}})
def disconnect_server(identifier):
    denied = _permission()
    if denied:
        return denied
    _server(identifier)
    connection = get_db()
    with connection:
        connection.execute(
            "UPDATE mcp_servers SET connected=0,tools_json='[]',last_error='' WHERE id=? AND class_id=?",
            (identifier, g.user["class_id"]),
        )
    return jsonify(server=_public_server(_server(identifier)))


@bp.get("/api/mcp/servers/<int:identifier>/tools")
@api_doc({"get": {"summary": "读取本班MCP发现工具", "x-response-schema": TOOLS_SCHEMA,
                   "x-error-statuses": ["403", "404"]}})
def server_tools(identifier):
    denied = _permission()
    if denied:
        return denied
    server = _server(identifier)
    return jsonify(server_id=identifier, tools=_decode_tools(server) if server["connected"] else [])


@bp.get("/api/mcp/tool-calls")
@api_doc({"get": {"summary": "列出本班MCP调用审计（最近200条）", "x-response-schema": AUDIT_SCHEMA,
                   "x-error-statuses": ["403"]}})
def tool_calls():
    denied = _permission()
    if denied:
        return denied
    rows = get_db().execute(
        "SELECT id,server_id,class_id,user_id,conversation_id,round,tool_ref,status,summary,created_at "
        "FROM mcp_audit WHERE class_id=? ORDER BY created_at DESC,id DESC LIMIT 200",
        (g.user["class_id"],),
    ).fetchall()
    return jsonify(tool_calls=[dict(row) for row in rows])


def record_tool_call(*, server_id, class_id, user_id, conversation_id, round_number,
                     tool_ref, status, summary):
    """Persist one call outcome; callers pass only a bounded, credential-free summary."""
    if not isinstance(tool_ref, str) or not isinstance(status, str) or not isinstance(summary, str):
        raise ValueError("invalid MCP audit fields")
    connection = get_db()
    with connection:
        connection.execute(
            "INSERT INTO mcp_audit(server_id,class_id,user_id,conversation_id,round,tool_ref,status,summary) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (server_id, class_id, user_id, conversation_id, round_number, tool_ref, status, summary[:1000]),
        )
