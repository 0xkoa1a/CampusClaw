from apitest.common import assert_db_value, json_body, request, require_columns


def run(context):
    payload = {
        "title": context["synthetic_prefix"] + "-async-grading",
        "question": "合成验收题：计算 1 + 1 并简述理由。",
        "reference_answer": "2。",
        "rubric": "答案正确得满分，错误得零分。仅使用本题合成内容。",
        "max_score": 100,
        "skill_id": None,
    }
    response = request(context, "POST", "/api/assignments",
                       token=context["tokens"]["teacher"], payload=payload)
    assert response[0] == 201, f"assignment creation expected HTTP 201, got {response[0]}"
    assignment = json_body(response)["assignment"]
    for field, value in payload.items():
        assert assignment[field] == value, f"assignment response field mismatch: {field}"
    require_columns(context, "assignments", {"id", "class_id", "teacher_id", *payload})
    teacher = assert_db_value(context, "users", "username", context["identities"]["teacher"]["username"])
    assert_db_value(context, "assignments", "id", assignment["id"], **payload,
                    class_id=context["identities"]["teacher"]["class_id"], teacher_id=teacher["id"])
    context["assignment_id"] = assignment["id"]
    context["assignment_max_score"] = payload["max_score"]
    student_view = json_body(request(context, "GET", f"/api/assignments/{assignment['id']}",
                                     token=context["tokens"]["student_a"]))["assignment"]
    assert not {"reference_answer", "rubric"} & student_view.keys(), "student response leaked teacher-only fields"
    foreign = request(context, "GET", f"/api/assignments/{assignment['id']}", token=context["tokens"]["student_b"])
    assert foreign[0] == 404, f"class B assignment read expected HTTP 404, got {foreign[0]}"
    return "Synthetic teacher assignment matches SQLite; student reference fields omitted; class B read denied with 404."
