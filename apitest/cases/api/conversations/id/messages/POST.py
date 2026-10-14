import json

from apitest.common import db_rows, request, require_columns


def run(context):
    prompt = context["synthetic_prefix"] + " 请仅根据本条合成提示简短回答。"
    status, headers, raw = request(context, "POST", f"/api/conversations/{context['conversation_id']}/messages",
                                   token=context["tokens"]["student_a"], payload={"content": prompt}, stream=True)
    assert status == 200 and "text/event-stream" in headers.get("Content-Type", ""), f"expected SSE, got HTTP {status}"
    events = []
    for block in raw.decode("utf-8").replace("\r\n", "\n").split("\n\n"):
        if block.strip():
            data = "\n".join(line[6:] for line in block.splitlines() if line.startswith("data: "))
            if data:
                event = json.loads(data)
                name = next((line[7:] for line in block.splitlines() if line.startswith("event: ")), None)
                if name:
                    event["type"] = name
                events.append(event)
    kind = lambda event: event.get("type", event.get("event"))
    assert events and kind(events[0]) == "meta" and kind(events[-1]) == "done", "SSE must run meta through done"
    assert {"status", "skill_name", "citations"} <= set(events[0]), "SSE meta is missing status, skill_name, or citations"
    assert all(kind(event) in {"meta", "delta", "done", "error"} for event in events)
    assert not any(kind(event) == "error" for event in events), "SSE emitted an error event"
    assert all(kind(event) == "delta" for event in events[1:-1]), "SSE events must follow meta, delta*, done order"
    deltas = [event.get("text", "") for event in events if kind(event) == "delta"]
    assert deltas, "SSE must contain delta events"
    message_id = events[-1]["message_id"]
    content = "".join(deltas)
    require_columns(context, "messages", {"id", "conversation_id", "role", "content", "status", "citations_json", "skill_name"})
    rows = db_rows(context, "messages", "id=?", (message_id,))
    assert len(rows) == 1 and rows[0]["conversation_id"] == context["conversation_id"]
    assert rows[0]["role"] == "assistant" and rows[0]["content"] == content and rows[0]["status"] == "complete"
    assert json.loads(rows[0]["citations_json"]) == events[0].get("citations", [])
    assert rows[0]["skill_name"] == events[0].get("skill_name")
    user_rows = db_rows(context, "messages", "conversation_id=? AND role='user'", (context["conversation_id"],))
    assert len(user_rows) == 1 and user_rows[0]["content"] == prompt
    conversation = db_rows(context, "conversations", "id=?", (context["conversation_id"],))[0]
    assert conversation["title"] == prompt[:24]
    context["message_id"] = message_id
    context["sse_events"] = events
    return "SSE meta/delta/done order and concatenated text match the persisted assistant message."
