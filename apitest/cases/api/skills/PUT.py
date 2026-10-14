from apitest.common import assert_db_value, json_body, request


def run(context):
    source = context["skill_source"].replace("只针对本次合成验收提示提供简短回答。", "更新后的合成验收技能仍只回答本次提示。")
    skill = json_body(request(context, "PUT", f"/api/skills/{context['skill_id']}", token=context["tokens"]["teacher"], payload={"source": source}))["skill"]
    assert skill["id"] == context["skill_id"] and skill["source_text"] == source
    context["skill_source"] = source
    assert_db_value(context, "skills", "id", skill["id"], source_text=source)
    return "Synthetic skill update matches SQLite."
