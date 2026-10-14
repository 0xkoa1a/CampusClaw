from apitest.common import db_rows, request


def run(context):
    status, _headers, body = request(context, "DELETE", f"/api/conversations/{context['conversation_id']}", token=context["tokens"]["student_a"])
    assert 200 <= status < 300, f"conversation delete returned HTTP {status}: {body[:300]!r}"
    assert not db_rows(context, "conversations", "id=?", (context["conversation_id"],)), "deleted conversation remains in SQLite"
    return "Synthetic conversation was deleted from SQLite."
