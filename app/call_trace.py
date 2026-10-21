"""Private per-turn evidence; never captures transport headers or credentials."""

import json
from contextvars import ContextVar

from .gateway import GatewayUnavailable

active_trace = ContextVar("active_trace", default=None)


def record(kind, payload):
    trace = active_trace.get()
    if trace is None:
        return
    event = {"kind": kind, "payload": payload}
    size = len(json.dumps(event, ensure_ascii=False).encode())
    if trace["bytes"] + size > 2_000_000:
        raise GatewayUnavailable("调用记录超过大小限制")
    trace["bytes"] += size
    # Copy now: callers append tool results to messages after sending requests.
    trace["events"].append(json.loads(json.dumps(event, ensure_ascii=False)))


def migrate_platform(connection):
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(agents)")}
    with connection:
        if "tool_names_json" not in columns:
            connection.execute("ALTER TABLE agents ADD COLUMN tool_names_json TEXT NOT NULL DEFAULT '[]'")
        connection.execute("""CREATE TABLE IF NOT EXISTS call_traces (
            id INTEGER PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            user_message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            events_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
