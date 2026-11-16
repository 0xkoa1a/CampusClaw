"""Request correlation and credential-safe structured HTTP logging."""

import json
import logging
import math
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from flask import Blueprint, g, has_app_context, has_request_context, jsonify, request

from .openapi import api_doc

bp = Blueprint("audit_events", __name__)
execution_context = ContextVar('audit_execution_context', default={})


class _CurrentStderr:
    """Resolve stderr at write time so test and server stream capture stays current."""

    def write(self, value):
        return sys.stderr.write(value)

    def flush(self):
        return sys.stderr.flush()


class SafeJsonFormatter(logging.Formatter):
    """Serialize only explicitly approved fields; never format exception text."""

    def format(self, record):
        event = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
        }
        for name in (
            "event", "request_id", "user_id", "username", "role", "class_id",
            "duration_ms", "status", "route", "path", "prompt_tokens",
            "completion_tokens", "total_tokens", "tool_ref", "task_id",
            "skill", "operation", "object", "usage",
        ):
            if hasattr(record, name):
                event[name] = getattr(record, name)
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


def _emit(event, **fields):
    logger = logging.getLogger("campusclaw.observability")
    logger.setLevel(logging.INFO)
    if not any(getattr(handler, "_campusclaw_json", False) for handler in logger.handlers):
        handler = logging.StreamHandler(_CurrentStderr())
        handler._campusclaw_json = True
        handler.setFormatter(SafeJsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    logger.info(event, extra={"event": event, **fields})
    if not has_app_context():
        return
    def safe_text(value):
        return value[:128] if isinstance(value, str) else None

    raw_usage = fields.get("usage")
    safe_usage = None
    if isinstance(raw_usage, dict):
        safe_usage = {
            key: raw_usage.get(key)
            if type(raw_usage.get(key)) is int and raw_usage[key] >= 0 else None
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
    allowed = {
        "route": safe_text(fields.get("route")),
        "status": fields.get("status") if type(fields.get("status")) is int else None,
        "duration_ms": fields.get("duration_ms") if (
            type(fields.get("duration_ms")) in (int, float)
            and math.isfinite(fields["duration_ms"])
        ) else None,
        "class_id": fields.get("class_id") if type(fields.get("class_id")) is int else None,
        "role": safe_text(fields.get("role")),
        "username": safe_text(fields.get("username")),
        "skill": safe_text(fields.get("skill")),
        "operation": safe_text(fields.get("operation")),
        "object": safe_text(fields.get("object")),
        "usage": safe_usage,
    }
    try:
        from .db import get_db
        with get_db():
            get_db().execute(
                "INSERT INTO audit_events(timestamp,level,event,request_id,user_id,fields_json) VALUES (?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    logging.getLevelName(logging.INFO), event,
                    fields.get("request_id"), fields.get("user_id"),
                    json.dumps(allowed, ensure_ascii=False, separators=(",", ":")),
                ),
            )
    except Exception:
        # Audit storage must not turn a completed request into a failure.
        logger.error("audit_persist_failed", extra={"event": "audit_persist_failed"})


def init_observability(app):
    """Install request IDs and safe JSON access logs on a Flask application."""
    if not app.extensions.get("campusclaw_observability"):
        if not app.logger.handlers:
            handler = logging.StreamHandler()
            app.logger.addHandler(handler)
        for handler in app.logger.handlers:
            handler.setFormatter(SafeJsonFormatter())
        app.extensions["campusclaw_observability"] = True
    else:
        for handler in app.logger.handlers:
            handler.setFormatter(SafeJsonFormatter())
    app.logger.propagate = False
    with app.app_context():
        from .db import get_db
        with get_db():
            get_db().execute("""CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                event TEXT NOT NULL,
                request_id TEXT,
                user_id INTEGER,
                fields_json TEXT NOT NULL DEFAULT '{}'
            )""")
            get_db().execute("CREATE INDEX IF NOT EXISTS idx_audit_events_user_time ON audit_events(user_id,timestamp DESC,id DESC)")

    if not app.extensions.get("campusclaw_observability_hooks"):
        app.extensions["campusclaw_observability_hooks"] = True

        @app.before_request
        def _start_observed_request():
            g.request_id = str(uuid.uuid4())
            g.request_started = time.monotonic()

        @app.after_request
        def _finish_observed_request(response):
            request_id = getattr(g, "request_id", None)
            if request_id is None:
                return response
            response.headers["X-Request-ID"] = request_id
            user = getattr(g, "user", None)
            elapsed = max(0.0, (time.monotonic() - g.request_started) * 1000)
            _emit(
                "http_request",
                request_id=request_id,
                user_id=user["id"] if user is not None else None,
                username=user["username"] if user is not None else None,
                role=user["role"] if user is not None else None,
                class_id=user["class_id"] if user is not None else None,
                duration_ms=round(elapsed, 3),
                status=response.status_code,
                route=request.url_rule.rule if request.url_rule else "unmatched",
                skill=getattr(g, "skill_name", None),
                operation=request.method,
                object=request.url_rule.rule if request.url_rule else "unmatched",
            )
            return response


def current_request_id():
    """Return the active request ID, or None outside a Flask request."""
    return getattr(g, "request_id", None) if has_request_context() else None


AUDIT_EVENT_SCHEMA = {"type": "object", "properties": {
    "id": {"type": "integer"}, "timestamp": {"type": "string", "format": "date-time"},
    "level": {"type": "string"}, "event": {"type": "string"},
    "request_id": {"type": "string", "nullable": True},
    "user_id": {"type": "integer", "nullable": True},
    "fields": {"type": "object", "properties": {
        "route": {"type": "string", "nullable": True},
        "status": {"type": "integer", "nullable": True},
        "duration_ms": {"type": "number", "nullable": True},
        "class_id": {"type": "integer", "nullable": True},
        "role": {"type": "string", "nullable": True},
        "username": {"type": "string", "nullable": True},
        "skill": {"type": "string", "nullable": True},
        "operation": {"type": "string", "nullable": True},
        "object": {"type": "string", "nullable": True},
        "usage": {"type": "object", "nullable": True, "properties": {
            "prompt_tokens": {"type": "integer", "nullable": True},
            "completion_tokens": {"type": "integer", "nullable": True},
            "total_tokens": {"type": "integer", "nullable": True},
        }},
    }},
}}

@bp.get("/api/audit-events")
@api_doc({"get": {
    "summary": "查询本班结构化审计事件",
    "x-response-schema": {"type": "object", "properties": {
        "audit_events": {"type": "array", "items": AUDIT_EVENT_SCHEMA},
    }},
    "x-error-statuses": ["400", "403"],
    "parameters": [
        {"name": "user_id", "in": "query", "schema": {"type": "integer", "minimum": 1}},
        {"name": "from", "in": "query", "schema": {"type": "string", "format": "date-time"}},
        {"name": "to", "in": "query", "schema": {"type": "string", "format": "date-time"}},
        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 200}},
    ],
}})
def audit_events():
    from datetime import datetime
    from .auth import require_user
    from .db import get_db
    denied = require_user()
    if denied:
        return denied
    if g.user["role"] != "teacher":
        return jsonify(error="需要教师权限"), 403

    allowed_args = {"user_id", "from", "to", "limit"}
    if set(request.args.keys()) - allowed_args or any(
        len(request.args.getlist(key)) != 1 for key in request.args.keys()
    ):
        return jsonify(error="查询参数无效"), 400

    filters = ["json_extract(fields_json,'$.class_id')=?"]
    params = [g.user["class_id"]]
    user_id = request.args.get("user_id")
    if user_id is not None:
        if not user_id.isdecimal() or not 1 <= int(user_id) <= 9223372036854775807:
            return jsonify(error="user_id 无效"), 400
        filters.append("user_id=?")
        params.append(int(user_id))
    parsed_times = {}
    for query_name, operator in (("from", ">="), ("to", "<=")):
        value = request.args.get(query_name)
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return jsonify(error=f"{query_name} 时间无效"), 400
            filters.append(f"timestamp{operator}?")
            parsed_times[query_name] = parsed.astimezone(timezone.utc)
            params.append(parsed_times[query_name].isoformat())
    if len(parsed_times) == 2 and parsed_times["from"] > parsed_times["to"]:
        return jsonify(error="时间范围无效"), 400
    raw_limit = request.args.get("limit", "100")
    if not raw_limit.isdecimal() or not 1 <= int(raw_limit) <= 200:
        return jsonify(error="limit 须为 1 到 200"), 400
    params.append(int(raw_limit))
    rows = get_db().execute(
        "SELECT id,timestamp,level,event,request_id,user_id,fields_json FROM audit_events WHERE "
        + " AND ".join(filters) + " ORDER BY timestamp DESC,id DESC LIMIT ?", params,
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["fields"] = json.loads(item.pop("fields_json"))
        result.append(item)
    return jsonify(audit_events=result)


def log_model_usage(usage, *, event="llm_usage", duration_ms=None):
    """Emit actual token counts only; absent or malformed counts remain null."""
    usage = usage if isinstance(usage, dict) else {}
    values = {}
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(field)
        values[field] = value if type(value) is int and value >= 0 else None
    user = getattr(g, "user", None) if has_request_context() else None
    worker = execution_context.get()
    fields = {
        "request_id": current_request_id(),
        "user_id": user["id"] if user is not None else None,
        "username": user["username"] if user is not None else None,
        "role": user["role"] if user is not None else None,
        "class_id": user["class_id"] if user is not None else None,
        "skill": getattr(g, "skill_name", None) if has_request_context() else None,
        **worker,
        **values,
        "usage": values,
    }
    if duration_ms is not None:
        fields["duration_ms"] = round(max(0.0, duration_ms), 3)
    _emit(event, **fields)
    return values
