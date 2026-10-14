from apitest.common import assert_db_value, json_body, request, require_columns


def run(context):
    payload = {"name": context["agent_name"], "role_prompt": "Answer only the synthetic acceptance prompt. Do not use private materials.",
               "enabled": True, "skill_ids": [], "material_ids": []}
    agent = json_body(request(context, "POST", "/api/agents", token=context["tokens"]["teacher"], payload=payload))["agent"]
    assert agent["name"] == payload["name"] and agent["role_prompt"] == payload["role_prompt"] and agent["enabled"] is True
    context["agent_id"], context["agent_role_prompt"] = agent["id"], payload["role_prompt"]
    require_columns(context, "agents", {"id", "name", "role_prompt", "enabled"})
    assert_db_value(context, "agents", "id", agent["id"], name=payload["name"], role_prompt=payload["role_prompt"], enabled=1)
    return "Synthetic no-material agent creation matches SQLite."
