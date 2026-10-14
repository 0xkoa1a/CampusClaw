from apitest.common import assert_db_value, json_body, request, require_columns


def run(context):
    source = (f"名称：{context['skill_name']}\n适用条件：{context['synthetic_prefix']}\n"
              "资料：\n工具：knowledge_search\n启用：是\n\n"
              "只针对本次合成验收提示提供简短回答。不要读取或引用任何私人材料。")
    context["skill_source"] = source
    body = json_body(request(context, "POST", "/api/skills", token=context["tokens"]["teacher"], payload={"source": source}))
    skill = body["skill"]
    assert skill["name"] == context["skill_name"] and skill["source_text"] == source and skill["enabled"] is True
    context["skill_id"] = skill["id"]
    require_columns(context, "skills", {"id", "name", "source_text", "enabled"})
    assert_db_value(context, "skills", "id", skill["id"], name=skill["name"], source_text=source, enabled=1)
    return "Synthetic skill creation matches the response and SQLite row."
