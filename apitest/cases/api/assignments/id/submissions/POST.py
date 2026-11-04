import hashlib
import json
import math
import time
import uuid

from apitest.common import assert_db_value, db_rows, json_body, request, require_columns


def run(context):
    assignment_id = context["assignment_id"]
    route = f"/api/assignments/{assignment_id}/submissions"
    student = assert_db_value(context, "users", "username", context["identities"]["student_a"]["username"])
    class_id = context["identities"]["student_a"]["class_id"]
    require_columns(context, "submissions", {"id", "assignment_id", "user_id", "class_id", "content", "content_hash", "idempotency_key"})
    require_columns(context, "grading_tasks", {"id", "submission_id", "user_id", "class_id", "status"})
    require_columns(context, "task_outbox", {"task_id"})
    content = context["synthetic_prefix"] + " 合成答案：1 + 1 = 2。"
    samples, accepted = [], []
    context["async_time_total"] = samples
    for index in range(20):
        key = str(uuid.uuid4())
        started = time.perf_counter()
        response = request(context, "POST", route, token=context["tokens"]["student_a"],
                           payload={"content": content}, headers={"Idempotency-Key": key})
        samples.append(time.perf_counter() - started)
        assert response[0] == 202, f"submission {index + 1} expected HTTP 202, got {response[0]}"
        body = json_body(response)
        assert "result" not in body, "acceptance response must not include a grading result"
        assert body["status"] == "pending" and body["replayed"] is False, "fresh acceptance must return pending, not replayed"
        assert body["task_id"] and body["submission_id"], "acceptance response missing identifiers"
        assert_db_value(context, "submissions", "id", body["submission_id"], assignment_id=assignment_id,
                        user_id=student["id"], class_id=class_id, content=content,
                        content_hash=hashlib.sha256(content.encode()).hexdigest(), idempotency_key=key)
        assert_db_value(context, "grading_tasks", "id", body["task_id"],
                        submission_id=body["submission_id"], user_id=student["id"], class_id=class_id)
        assert_db_value(context, "task_outbox", "task_id", body["task_id"])
        accepted.append(body)
        if index == 0:
            context["async_first_key"] = key
    assert len({item["task_id"] for item in accepted}) == 20, "independent keys must create 20 distinct tasks"
    assert len({item["submission_id"] for item in accepted}) == 20, "independent keys must create 20 distinct submissions"
    context["async_first_task_id"] = accepted[0]["task_id"]
    context["async_first_submission_id"] = accepted[0]["submission_id"]
    headers = {"Idempotency-Key": context["async_first_key"]}
    replay = request(context, "POST", route, token=context["tokens"]["student_a"], payload={"content": content}, headers=headers)
    assert replay[0] == 202, f"replay expected HTTP 202, got {replay[0]}"
    replay_body = json_body(replay)
    assert "result" not in replay_body and replay_body["replayed"] is True
    assert replay_body["task_id"] == accepted[0]["task_id"] and replay_body["submission_id"] == accepted[0]["submission_id"]
    conflict = request(context, "POST", route, token=context["tokens"]["student_a"],
                       payload={"content": content + " 已修改"}, headers=headers)
    assert conflict[0] == 409, f"same key with changed content expected HTTP 409, got {conflict[0]}"
    foreign = request(context, "POST", route, token=context["tokens"]["student_b"],
                      payload={"content": content}, headers={"Idempotency-Key": str(uuid.uuid4())})
    assert foreign[0] == 404, f"class B submission expected HTTP 404, got {foreign[0]}"
    rows = db_rows(context, "submissions", "assignment_id=?", (assignment_id,))
    assert {row["id"] for row in rows} == {item["submission_id"] for item in accepted}, "replay/conflict/foreign request changed submission set"
    for item in accepted:
        assert_db_value(context, "grading_tasks", "submission_id", item["submission_id"], id=item["task_id"])
        assert_db_value(context, "task_outbox", "task_id", item["task_id"])
    p95 = sorted(samples)[math.ceil(.95 * len(samples)) - 1]
    context["async_p95_seconds"] = p95
    metrics = {"samples": 20, "time_total_seconds": [round(value, 6) for value in samples],
               "p95_seconds": round(p95, 6), "all_202_without_result": True,
               "sqlite_submission_task_outbox_match": True, "same_key_same_task": True,
               "changed_content_409": True, "class_b_404": True}
    return json.dumps(metrics, ensure_ascii=False) + "; consumer unchanged; real-broker durability and restart recovery not tested."
