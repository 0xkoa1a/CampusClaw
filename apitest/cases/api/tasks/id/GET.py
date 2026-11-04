import math
import time

from apitest.common import assert_db_value, db_rows, json_body, request, require_columns


def run(context):
    task_id = context["async_first_task_id"]
    submission_id = context["async_first_submission_id"]
    route = f"/api/tasks/{task_id}"
    foreign = request(context, "GET", route, token=context["tokens"]["student_b"])
    assert foreign[0] == 404, f"class B task read expected HTTP 404, got {foreign[0]}"
    budget = float(context.get("grading_timeout", context.get("timeout", 60)))
    assert math.isfinite(budget) and budget > 0, "grading polling timeout must be finite and positive"
    deadline = time.monotonic() + budget
    last_status = "not-polled"
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        polling_context = dict(context, timeout=min(float(context.get("timeout", 60)), remaining))
        task = json_body(request(polling_context, "GET", route, token=context["tokens"]["student_a"]))["task"]
        assert task["id"] == task_id and task["submission_id"] == submission_id
        assert task["assignment_id"] == context["assignment_id"]
        assert not {"reference_answer", "rubric"} & task.keys(), "task response leaked teacher-only fields"
        last_status = task["status"]
        assert last_status not in {"failed", "dead"}, f"grading ended in {last_status}; success not observed"
        if last_status == "succeeded":
            break
        assert last_status in {"pending", "running"}, f"unknown task status: {last_status}"
        assert task["result"] is None, "nonterminal task must not expose a completed result"
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(.5, remaining))
    else:
        raise AssertionError(f"grading did not succeed within {budget:g}s; last status={last_status}; consumer was not changed")
    result = task["result"]
    assert isinstance(result, dict), "successful task missing result"
    score = result.get("score")
    assert type(score) in (int, float) and math.isfinite(score) and 0 <= score <= context["assignment_max_score"]
    assert isinstance(result.get("feedback"), str) and result["feedback"].strip(), "successful task missing feedback"
    assert isinstance(result.get("source"), str) and result["source"], "successful task missing source"
    require_columns(context, "grading_results", {"id", "submission_id", "task_id", "score", "feedback", "source"})
    row = assert_db_value(context, "grading_results", "submission_id", submission_id, task_id=task_id, **result)
    assert_db_value(context, "grading_results", "task_id", task_id, id=row["id"])
    assert_db_value(context, "grading_tasks", "id", task_id, status="succeeded", submission_id=submission_id)
    assert_db_value(context, "task_outbox", "task_id", task_id)
    repeated = json_body(request(context, "GET", route, token=context["tokens"]["student_a"]))["task"]
    assert repeated["status"] == "succeeded" and repeated["result"] == result
    assert len(db_rows(context, "grading_results", "submission_id=? OR task_id=?", (submission_id, task_id))) == 1
    source = {"test-provider": "local deterministic test-provider", "real-gateway": "course gateway"}.get(result["source"], "other backend source")
    return f"First task succeeded with one SQLite result; repeated GET unchanged; source={source}. Real-broker durability, restart and redelivery not tested."
