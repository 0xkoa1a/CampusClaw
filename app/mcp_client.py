"""Bounded HTTP MCP teaching subset, without credentials in diagnostics."""

import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .gateway import GatewayUnavailable
from .call_trace import record


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def rpc(base_url, token, method, params=None):
    if not isinstance(token, str) or not token:
        raise GatewayUnavailable("MCP 令牌未配置")
    identifier = secrets.token_hex(8)
    payload = {"jsonrpc": "2.0", "id": identifier, "method": method, "params": params or {}}
    record("mcp_request", payload)
    req = Request(base_url.rstrip("/") + "/mcp", method="POST",
                  data=json.dumps(payload, ensure_ascii=False).encode(),
                  headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                           "Accept": "application/json, text/event-stream"})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=5) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("oversized response")
            data = json.loads(raw)
        if not isinstance(data, dict) or data.get("jsonrpc") != "2.0" or data.get("id") != identifier or "error" in data or "result" not in data:
            raise ValueError("invalid JSON-RPC response")
        record("mcp_response", data)
        return data["result"]
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError) as exc:
        raise GatewayUnavailable("MCP 服务连接或协议错误") from exc


def discover(base_url, token):
    from jsonschema import Draft202012Validator
    result = rpc(base_url, token, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "CampusClaw", "version": "1.0"}})
    if not isinstance(result, dict) or result.get("protocolVersion") != "2025-06-18" or "tools" not in result.get("capabilities", {}):
        raise GatewayUnavailable("MCP 服务未提供兼容 tools 能力")
    # The course's stateless HTTP subset does not create MCP session IDs.
    result = rpc(base_url, token, "tools/list")
    tools = result.get("tools") if isinstance(result, dict) else None
    import re
    if not isinstance(tools, list) or len(tools) > 32:
        raise GatewayUnavailable("MCP 工具清单不正确")
    seen = set()
    for tool in tools:
        if not isinstance(tool, dict) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", tool.get("name", "")) or tool["name"] in seen:
            raise GatewayUnavailable("MCP 工具名称不正确")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object" or "$ref" in json.dumps(schema):
            raise GatewayUnavailable("MCP 参数结构不正确或含外部引用")
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            raise GatewayUnavailable("MCP 参数 schema 不正确") from exc
        if not isinstance(tool.get("description", ""), str) or len(tool.get("description", "")) > 2000:
            raise GatewayUnavailable("MCP 工具说明超限")
        seen.add(tool["name"])
    return tools
