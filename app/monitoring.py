"""Teacher-only classroom metrics and persistent in-app alert records."""

import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, render_template, request

from .auth import require_user
from .db import get_db
from .openapi import api_doc

bp = Blueprint("monitoring", __name__)
WINDOWS = (300, 3600, 21600, 86400, 604800)


def _now():
    return datetime.now(timezone.utc)


def _ensure_alert_table():
    get_db().execute("""CREATE TABLE IF NOT EXISTS monitor_alerts (
        id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL,
        skill TEXT NOT NULL, start_at TEXT NOT NULL, end_at TEXT,
        threshold REAL NOT NULL, error_rate REAL NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','active','resolved')),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    get_db().execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_monitor_alert_open
        ON monitor_alerts(class_id,skill) WHERE status IN ('pending','active')""")


def _teacher():
    denied = require_user()
    if denied:
        return denied
    if g.user["role"] != "teacher":
        return jsonify(error="需要教师权限"), 403
    return None


def _event_status_is_error(status):
    if isinstance(status, bool) or status is None:
        return False
    if isinstance(status, (int, float)):
        return status >= 400
    return str(status).lower() in {"error", "failed", "failure", "denied"}


def _skill_events(class_id, start):
    rows = get_db().execute("""SELECT timestamp,fields_json FROM audit_events
        WHERE event='skill_invocation'
          AND json_extract(fields_json,'$.class_id')=? AND timestamp>=?
          AND json_extract(fields_json,'$.skill') IS NOT NULL
        ORDER BY timestamp,id""", (class_id, (start - timedelta(seconds=1)).isoformat())).fetchall()
    events = []
    for row in rows:
        try:
            fields = json.loads(row["fields_json"])
            stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            stamp = stamp.astimezone(timezone.utc)
            skill = fields.get("skill")
            # HTTP access rows may carry a route in `skill` for legacy compatibility.
            # A route-shaped value is never counted as a skill invocation.
            if (stamp >= start and stamp <= _now() and isinstance(skill, str) and skill.strip()
                    and skill not in {fields.get("route"), fields.get("object")}):
                events.append((stamp, skill[:128], fields.get("status")))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return events


def _record_alerts(class_id, events, now, duration, threshold):
    earliest = now - timedelta(seconds=duration)
    by_skill = {}
    for stamp, skill, status in events:
        if stamp >= earliest:
            by_skill.setdefault(skill, []).append((stamp, status))

    rates = {}
    for skill, calls in by_skill.items():
        failures = sum(_event_status_is_error(status) for _, status in calls)
        rates[skill] = failures / len(calls)
        existing = get_db().execute("SELECT id,start_at,updated_at,status FROM monitor_alerts WHERE class_id=? AND skill=? AND status IN ('pending','active')", (class_id, skill)).fetchone()
        observation_continues = bool(existing and
            (now - datetime.fromisoformat(existing["updated_at"])).total_seconds() <= max(1, duration / 4))
        if rates[skill] > threshold and existing and observation_continues:
            start_at = existing["start_at"]
            observed_seconds = (now - datetime.fromisoformat(start_at)).total_seconds()
            status = "active" if observed_seconds >= duration else "pending"
            get_db().execute("UPDATE monitor_alerts SET end_at=?,error_rate=?,status=?,updated_at=? WHERE id=?", (now.isoformat(), rates[skill], status, now.isoformat(), existing["id"]))
        elif rates[skill] > threshold:
            if existing:
                get_db().execute("UPDATE monitor_alerts SET status='resolved',end_at=?,updated_at=? WHERE id=?", (now.isoformat(), now.isoformat(), existing["id"]))
            get_db().execute("""INSERT INTO monitor_alerts
                (class_id,skill,start_at,end_at,threshold,error_rate,status,created_at,updated_at)
                VALUES (?,?,?,NULL,?,?,'pending',?,?)""", (class_id, skill, now.isoformat(), threshold, rates[skill], now.isoformat(), now.isoformat()))

    active_rows = get_db().execute("SELECT id,skill FROM monitor_alerts WHERE class_id=? AND status IN ('pending','active')", (class_id,)).fetchall()
    for row in active_rows:
        if row["skill"] not in by_skill or rates.get(row["skill"], 0) <= threshold:
            get_db().execute("UPDATE monitor_alerts SET status='resolved',end_at=?,updated_at=? WHERE id=?", (now.isoformat(), now.isoformat(), row["id"]))


def _dashboard(duration):
    now = _now()
    start = now - timedelta(seconds=duration)
    class_id = g.user["class_id"]
    events = _skill_events(class_id, start)
    threshold = float(current_app.config.get("MONITOR_ALERT_ERROR_RATE_THRESHOLD", 0.01))
    alert_window = int(current_app.config.get("MONITOR_ALERT_WINDOW_SECONDS", 300))
    recent_events = _skill_events(class_id, now - timedelta(seconds=alert_window))
    # Evaluate alert persistence only when source events span the complete configured window.
    _record_alerts(class_id, recent_events, now, alert_window, threshold)

    counts_by_skill = {}
    for _, skill, _ in events:
        counts_by_skill[skill] = counts_by_skill.get(skill, 0) + 1
    skills = sorted(counts_by_skill, key=lambda name: (-counts_by_skill[name], name))[:3]
    events = [event for event in events if event[1] in skills]
    calls = {skill: 0 for skill in skills}
    errors = {skill: 0 for skill in skills}
    buckets = max(1, min(60, duration // 60))
    step = duration / buckets
    series = {skill: [0] * buckets for skill in skills}
    for stamp, skill, status in events:
        calls[skill] += 1
        errors[skill] += int(_event_status_is_error(status))
        index = min(buckets - 1, max(0, int((stamp - start).total_seconds() / step)))
        series[skill][index] += 1
    error_rates = [{"skill": skill, "calls": calls[skill], "errors": errors[skill],
                    "rate": errors[skill] / calls[skill] if calls[skill] else None} for skill in skills]

    http_rows = get_db().execute("""SELECT fields_json FROM audit_events
        WHERE json_extract(fields_json,'$.class_id')=? AND event='http_request' AND timestamp>=?""", (class_id, start.isoformat())).fetchall()
    durations = []
    for row in http_rows:
        try:
            value = json.loads(row["fields_json"]).get("duration_ms")
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                durations.append(float(value))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    durations.sort()
    p95 = durations[max(0, int(0.95 * len(durations) + 0.999999) - 1)] if durations else None
    queue_rows = get_db().execute("SELECT status,COUNT(*) AS n FROM grading_tasks WHERE class_id=? AND status IN ('pending','running') GROUP BY status", (class_id,)).fetchall()
    queue = {"pending": 0, "running": 0}
    for row in queue_rows:
        queue[row["status"]] = row["n"]

    alert_rows = get_db().execute("""SELECT id,skill,start_at,end_at,threshold,error_rate,status,created_at,updated_at
        FROM monitor_alerts WHERE class_id=? ORDER BY created_at DESC,id DESC LIMIT 100""", (class_id,)).fetchall()
    return {"window_seconds": duration, "from": start.isoformat(), "to": now.isoformat(),
            "has_skill_data": bool(events), "skills": skills,
            "invocations": {"bucket_seconds": step, "labels": [round(i * step) for i in range(buckets)],
                            "series": [{"skill": skill, "values": series[skill]} for skill in skills]},
            "error_rates": error_rates, "http_p95_ms": p95, "http_sample_count": len(durations),
            "queue": queue, "alerts": [dict(row) for row in alert_rows],
            "alert_policy": {"window_seconds": alert_window, "threshold": threshold}}


@bp.get("/monitoring")
def monitoring_page():
    denied = _teacher()
    if denied:
        return denied
    return render_template("monitoring.html")


@bp.get("/api/monitoring")
@api_doc({"get": {
    "summary": "查询本班观测面板数据并记录持续错误率告警",
    "x-response-schema": {"type": "object", "properties": {
        "window_seconds": {"type": "integer"}, "skills": {"type": "array", "items": {"type": "string"}},
        "invocations": {"type": "object"}, "error_rates": {"type": "array"},
        "http_p95_ms": {"type": "number", "nullable": True}, "queue": {"type": "object"},
        "alerts": {"type": "array"}}},
    "x-error-statuses": ["400", "403"],
    "parameters": [{"name": "window", "in": "query", "schema": {"type": "integer", "enum": list(WINDOWS)}}],
}})
def monitoring_api():
    denied = _teacher()
    if denied:
        return denied
    raw = request.args.get("window", "3600")
    if not raw.isdecimal() or int(raw) not in WINDOWS:
        return jsonify(error="window 须为 300、3600、21600、86400 或 604800 秒"), 400
    _ensure_alert_table()
    return jsonify(_dashboard(int(raw)))
