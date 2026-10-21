"""HTTP JSON-RPC MCP teaching server for CampusClaw."""

import hmac
import math
import os

from flask import Flask, jsonify, request


PROTOCOL_VERSION = "2025-06-18"
MAX_ABS_VALUE = 1_000_000_000

TOOLS = [
    {
        "name": "calculate",
        "description": "对两个有限范围内的数字执行四则运算；计算结果绝对值也不得超过 1e9。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                },
                "a": {"type": "number", "minimum": -MAX_ABS_VALUE, "maximum": MAX_ABS_VALUE},
                "b": {"type": "number", "minimum": -MAX_ABS_VALUE, "maximum": MAX_ABS_VALUE},
            },
            "required": ["operation", "a", "b"],
            "additionalProperties": False,
        },
    },
    {
        "name": "unit_convert",
        "description": "在支持的长度单位或质量单位之间换算数值，不访问或修改外部状态。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "value": {"type": "number", "minimum": -MAX_ABS_VALUE, "maximum": MAX_ABS_VALUE},
                "from_unit": {"type": "string", "enum": ["m", "km", "cm", "mm", "kg", "g"]},
                "to_unit": {"type": "string", "enum": ["m", "km", "cm", "mm", "kg", "g"]},
            },
            "required": ["value", "from_unit", "to_unit"],
            "additionalProperties": False,
        },
    },
]

_UNIT_DEFINITIONS = {
    "m": ("length", 1.0),
    "km": ("length", 1000.0),
    "cm": ("length", 0.01),
    "mm": ("length", 0.001),
    "kg": ("mass", 1.0),
    "g": ("mass", 0.001),
}


def _rpc_error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(text, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _valid_number(value):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= MAX_ABS_VALUE


def _calculate(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"operation", "a", "b"}:
        return _tool_result("arguments 必须且只能包含 operation、a、b", True)
    operation, a, b = (arguments[key] for key in ("operation", "a", "b"))
    if not isinstance(operation, str) or operation not in {"add", "subtract", "multiply", "divide"}:
        return _tool_result("operation 必须是 add、subtract、multiply 或 divide", True)
    if not _valid_number(a) or not _valid_number(b):
        return _tool_result("a 和 b 必须是绝对值不超过 1e9 的有限数字", True)
    if operation == "divide" and b == 0:
        return _tool_result("除数不能为零", True)
    result = {
        "add": lambda: a + b,
        "subtract": lambda: a - b,
        "multiply": lambda: a * b,
        "divide": lambda: a / b,
    }[operation]()
    if not _valid_number(result):
        return _tool_result("计算结果必须是绝对值不超过 1e9 的有限数字", True)
    return _tool_result(str(result))


def _unit_convert(arguments):
    if not isinstance(arguments, dict) or set(arguments) != {"value", "from_unit", "to_unit"}:
        return _tool_result("arguments 必须且只能包含 value、from_unit、to_unit", True)
    value, from_unit, to_unit = (arguments[key] for key in ("value", "from_unit", "to_unit"))
    if not _valid_number(value):
        return _tool_result("value 必须是绝对值不超过 1e9 的有限数字", True)
    if not isinstance(from_unit, str) or not isinstance(to_unit, str) or from_unit not in _UNIT_DEFINITIONS or to_unit not in _UNIT_DEFINITIONS:
        return _tool_result("单位必须是 m、km、cm、mm、kg 或 g", True)
    from_dimension, from_scale = _UNIT_DEFINITIONS[from_unit]
    to_dimension, to_scale = _UNIT_DEFINITIONS[to_unit]
    if from_dimension != to_dimension:
        return _tool_result("不能在长度单位和质量单位之间换算", True)
    result = value * from_scale / to_scale
    if not math.isfinite(result) or abs(result) > MAX_ABS_VALUE:
        return _tool_result("换算结果超出允许范围", True)
    return _tool_result(f"{value} {from_unit} = {result} {to_unit}")


def _dispatch(message):
    request_id = message.get("id") if isinstance(message, dict) else None
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return _rpc_error(request_id, -32600, "Invalid Request"), 200
    method = message["method"]
    params = message.get("params", {})
    if not isinstance(params, dict):
        return _rpc_error(request_id, -32602, "Invalid params"), 200
    if method == "initialize":
        if params.get("protocolVersion") != PROTOCOL_VERSION:
            return _rpc_error(request_id, -32602, "Unsupported protocol version"), 200
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": "campusclaw-mcp-server", "version": "1.0.0"},
            "capabilities": {"tools": {}},
        }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}, 200
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}, 200
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments")
        if name == "calculate":
            result = _calculate(arguments)
        elif name == "unit_convert":
            result = _unit_convert(arguments)
        else:
            result = _tool_result("未知工具", True)
        return {"jsonrpc": "2.0", "id": request_id, "result": result}, 200
    return _rpc_error(request_id, -32601, "Method not found"), 200


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 65536

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/mcp")
    def mcp():
        expected = os.environ.get("MCP_AUTH_TOKEN", "")
        authorization = request.headers.get("Authorization", "")
        prefix = "Bearer "
        supplied = authorization[len(prefix):] if authorization.startswith(prefix) else ""
        if not expected or not supplied or not hmac.compare_digest(supplied, expected):
            return jsonify(error="unauthorized"), 401
        if request.headers.get("Origin"):
            return jsonify(error="browser origins are not allowed"), 403
        message = request.get_json(silent=True)
        if not isinstance(message, dict):
            return jsonify(_rpc_error(None, -32700, "Parse error")), 200
        if message.get("method") == "notifications/initialized" and message.get("jsonrpc") == "2.0":
            return "", 202
        response, status = _dispatch(message)
        return jsonify(response), status

    return app


app = create_app()
