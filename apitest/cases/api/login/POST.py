from apitest.common import json_body, request


def run(context):
    users = (("teacher", "teacher_a", "SEED_TEACHER_PASSWORD"),
             ("student_a", "student_a1", "SEED_STUDENT_A_PASSWORD"),
             ("student_b", "student_b1", "SEED_STUDENT_B_PASSWORD"))
    for role, username, secret_name in users:
        body = json_body(request(context, "POST", "/api/login", payload={
            "username": username, "password": context["secrets"][secret_name], "auth_mode": "bearer"}))
        assert body.get("token_type") == "Bearer" and body.get("access_token"), "login did not return a bearer token"
        context["tokens"][role] = body["access_token"]
        context["identities"][role] = {"username": username, "class_id": body["class_id"]}
    assert context["identities"]["teacher"]["class_id"] == context["identities"]["student_a"]["class_id"]
    assert context["identities"]["student_b"]["class_id"] != context["identities"]["student_a"]["class_id"]
    return "Seeded teacher and student bearer sessions initialized in process memory."
