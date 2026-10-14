import json

from apitest.common import db_rows, json_body, request


def run(context):
    body = json_body(request(context, "GET", f"/api/conversations/{context['conversation_id']}", token=context["tokens"]["student_a"]))
    assert body["conversation"]["id"] == context["conversation_id"] and isinstance(body.get("messages"), list)
    assert all({"role", "content", "status", "citations", "skill_name"} <= set(message) for message in body["messages"])
    rows = db_rows(context, "messages", "conversation_id=? ORDER BY id", (context["conversation_id"],))
    assert len(body["messages"]) == len(rows) == 2
    for actual, stored in zip(body["messages"], rows):
        assert actual["role"] == stored["role"] and actual["content"] == stored["content"]
        assert actual["status"] == stored["status"] and actual["citations"] == json.loads(stored["citations_json"])
        assert actual["skill_name"] == stored["skill_name"]
    assert body["conversation"].get("title") == rows[0]["content"][:24]
    return "Conversation detail returned its message history."
