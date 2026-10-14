from apitest.common import db_rows, request


def run(context):
    status, _headers, body = request(context, "DELETE", f"/api/skills/{context['skill_id']}", token=context["tokens"]["teacher"])
    assert 200 <= status < 300, f"skill delete returned HTTP {status}: {body[:300]!r}"
    rows = db_rows(context, "skills", "id=?", (context["skill_id"],))
    assert not rows or rows[0].get("enabled") in (0, False), "deleted skill remains enabled"
    return "Synthetic skill is deleted or disabled in SQLite."
