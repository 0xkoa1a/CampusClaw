from apitest.common import json_body, request


def run(context):
    for role in ("teacher", "student_a", "student_b"):
        body = json_body(request(context, "GET", "/api/me", token=context["tokens"][role]))
        assert body["username"] == context["identities"][role]["username"]
        assert body["class_id"] == context["identities"][role]["class_id"]
    return "Bearer identities match the seeded users and class assignments."
