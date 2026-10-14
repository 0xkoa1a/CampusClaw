from apitest.common import assert_db_value, json_body, request


def run(context):
    payload = {"name": context["agent_name"], "role_prompt": context["agent_role_prompt"] + " Prefer concise responses.",
               "enabled": True, "skill_ids": [], "material_ids": []}
    agent = json_body(request(context, "PUT", f"/api/agents/{context['agent_id']}", token=context["tokens"]["teacher"], payload=payload))["agent"]
    assert agent["id"] == context["agent_id"] and agent["role_prompt"] == payload["role_prompt"]
    context["agent_role_prompt"] = payload["role_prompt"]
    assert_db_value(context, "agents", "id", agent["id"], role_prompt=payload["role_prompt"])
    return "Synthetic agent update matches SQLite."
