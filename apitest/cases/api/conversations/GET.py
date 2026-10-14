from apitest.common import json_body, request


def run(context):
    own = json_body(request(context, "GET", "/api/conversations", token=context["tokens"]["student_a"]))["conversations"]
    other = json_body(request(context, "GET", "/api/conversations", token=context["tokens"]["student_b"]))["conversations"]
    assert any(item["id"] == context["conversation_id"] for item in own)
    assert all(item.get("id") != context["conversation_id"] for item in other)
    return "Conversation list is visible to its owner and isolated from another student."
