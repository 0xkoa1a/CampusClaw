from apitest.common import assert_db_value, json_body, request, require_columns


def run(context):
    conv = json_body(request(context, "POST", "/api/conversations", token=context["tokens"]["student_a"], payload={"agent_id": context["agent_id"]}))["conversation"]
    assert conv["agent_id"] == context["agent_id"]
    context["conversation_id"] = conv["id"]
    require_columns(context, "conversations", {"id", "user_id", "class_id", "agent_id", "title"})
    assert_db_value(context, "conversations", "id", conv["id"], agent_id=context["agent_id"], class_id=context["identities"]["student_a"]["class_id"])
    return "Student conversation ownership and agent assignment match SQLite."
