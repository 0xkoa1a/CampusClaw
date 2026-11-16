"""Prepare an isolated Week 9/10 evidence service using only local stubs."""

import argparse
import hashlib
import json
import sys
import uuid
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.week05_evidence_server import make_app as make_week05_app


HOST = "127.0.0.1"
PORT = 18090
BENCH_TASK_COUNT = 20_000

ACCOUNTS = {
    "teacher_a": "teacher-test-password",
    "student_a1": "student-a-test-password",
    "student_b1": "student-b-test-password",
}

SKILLS = (
    {
        "name": "数学解题引导",
        "trigger": "数学,方程,未知数,去括号",
        "subject": "数学",
        "body": "只指出下一步应检查或尝试什么；不提供最终答案、得数或完整过程。",
        "agent": "数学解题助手",
        "prompt": "你是耐心的数学老师，帮助学生自己找到下一步。回答简短。",
        "material_indexes": (0,),
        "question": "数学方程两边做相同运算后，我应该先检查哪一步？",
    },
    {
        "name": "错题讲解",
        "trigger": "错题,错误,检查,负号,去括号",
        "subject": "数学",
        "body": "定位错误所在步骤，说明应如何检查，并引导学生自己修正；不要整段复述标准答案。",
        "agent": "错题讲解助手",
        "prompt": "你帮助学生理解错误原因，只给检查线索，不替学生写完整答案。",
        "material_indexes": (0,),
        "question": "这道错题在去括号时负号处理错了，我应该先检查哪里？",
    },
    {
        "name": "材料问答",
        "trigger": "材料,讲义,资料,内容",
        "subject": "数学",
        "body": "只根据已提供的课程材料简短回答；材料不足时明确说明，并标明材料出处。",
        "agent": "材料问答助手",
        "prompt": "你是课程材料助手，根据材料回答并说明依据；资料不足时直说。",
        "material_indexes": (0, 1),
        "question": "请根据数学材料讲义，说明方程两边做相同运算有什么作用。",
    },
)


def require_status(response, expected, action):
    if response.status_code != expected:
        detail = response.get_data(as_text=True)[:1000]
        raise RuntimeError(f"{action}: expected HTTP {expected}, got {response.status_code}: {detail}")


def login(client, username):
    response = client.post(
        "/api/login",
        json={"username": username, "password": ACCOUNTS[username]},
    )
    require_status(response, 200, f"login {username}")


def skill_source(item):
    return (
        f"名称：{item['name']}\n"
        f"适用条件：{item['trigger']}\n"
        f"资料：{item['subject']}\n"
        "工具：knowledge_search\n"
        "启用：是\n\n"
        f"{item['body']}"
    )


def configure_skills(teacher, app):
    response = teacher.get("/api/skills")
    require_status(response, 200, "list skills")
    existing = {skill["name"]: skill for skill in response.json["skills"]}
    configured = {}
    for item in SKILLS:
        source = skill_source(item)
        current = existing.get(item["name"])
        if current:
            response = teacher.put(f"/api/skills/{current['id']}", json={"source": source})
        else:
            response = teacher.post("/api/skills", json={"source": source})
        require_status(response, 200 if current else 201, f"configure skill {item['name']}")
        skill = response.json["skill"]
        if skill["name"] != item["name"] or not skill["enabled"]:
            raise RuntimeError(f"skill {item['name']} is not enabled")
        configured[item["name"]] = skill

    fixture = app.extensions["week05_fixture"]
    material_ids = fixture["material_ids"]
    if len(material_ids) < 2:
        raise RuntimeError("Week 5 fixture did not create the expected synthetic materials")
    return configured, material_ids, fixture["agent_id"]


def configure_agents(teacher, skills, material_ids, seeded_agent_id):
    response = teacher.get("/api/agents")
    require_status(response, 200, "list agents")
    existing = {agent["name"]: agent for agent in response.json["agents"]}
    agents = {}
    for item in SKILLS:
        payload = {
            "name": item["agent"],
            "role_prompt": item["prompt"],
            "enabled": True,
            "skill_ids": [skills[item["name"]]["id"]],
            "material_ids": [material_ids[index] for index in item["material_indexes"]],
        }
        current = existing.get(item["agent"])
        # Reuse the factory's math agent, and keep setup repeatable for the two others.
        if item["name"] == "数学解题引导" and current is None:
            current = next((agent for agent in response.json["agents"]
                            if agent["id"] == seeded_agent_id), None)
            if current:
                payload["name"] = current["name"]
        if current:
            response = teacher.put(f"/api/agents/{current['id']}", json=payload)
        else:
            response = teacher.post("/api/agents", json=payload)
        require_status(response, 200 if current else 201, f"configure agent {item['agent']}")
        agent = response.json["agent"]
        if not agent["enabled"] or agent["skill_ids"] != payload["skill_ids"]:
            raise RuntimeError(f"agent {item['agent']} is not enabled with its skill")
        agents[item["name"]] = agent
    return agents


def exercise_agent(student, item, agent):
    response = student.post("/api/conversations", json={"agent_id": agent["id"]})
    require_status(response, 201, f"create conversation for {item['agent']}")
    conversation_id = response.json["conversation"]["id"]
    response = student.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": item["question"]},
        buffered=True,
    )
    require_status(response, 200, f"send normal question to {item['agent']}")
    stream = response.get_data(as_text=True)
    if "event: done" not in stream or "event: error" in stream:
        raise RuntimeError(f"{item['agent']} did not produce a completed local-stub response")
    saved = student.get(f"/api/conversations/{conversation_id}")
    require_status(saved, 200, f"read conversation for {item['agent']}")
    messages = saved.json["messages"]
    if not any(message["role"] == "assistant" and message["status"] == "complete"
               for message in messages):
        raise RuntimeError(f"{item['agent']} response was not persisted")
    return conversation_id


def create_bench_fixture(app, teacher, student):
    response = teacher.post("/api/assignments", json={
        "title": "Week 9/10 localstub 列表查询基准作业",
        "question": "仅用于本地任务列表查询基准，不调用批改模型。",
        "reference_answer": "合成基准数据",
        "rubric": "不用于评分",
        "max_score": 100,
    })
    require_status(response, 201, "create synthetic assignment")
    assignment_id = response.json["assignment"]["id"]

    from app.db import get_db

    with app.app_context():
        db = get_db()
        teacher_row = db.execute("SELECT id,class_id FROM users WHERE username='teacher_a'").fetchone()
        student_row = db.execute("SELECT id,class_id FROM users WHERE username='student_a1'").fetchone()
        if not teacher_row or not student_row or teacher_row["class_id"] != student_row["class_id"]:
            raise RuntimeError("synthetic teacher/student fixture identity is missing")
        max_attempts = app.config["TASK_MAX_ATTEMPTS"]
        db.execute("BEGIN IMMEDIATE")
        try:
            first_id = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM submissions").fetchone()[0]
            submission_rows = []
            task_rows = []
            for offset in range(BENCH_TASK_COUNT):
                content = f"localstub synthetic list-benchmark submission {offset:05d}"
                key = f"localstub-bench-{offset:05d}"
                submission_rows.append((
                    assignment_id, student_row["class_id"], student_row["id"],
                    content, hashlib.sha256(content.encode("utf-8")).hexdigest(), key,
                ))
                task_rows.append((
                    f"localstub-bench-{offset:05d}", first_id + offset,
                    student_row["class_id"], student_row["id"], max_attempts,
                ))
            db.executemany(
                """INSERT INTO submissions
                   (assignment_id,class_id,user_id,content,content_hash,idempotency_key)
                   VALUES (?,?,?,?,?,?)""",
                submission_rows,
            )
            db.executemany(
                """INSERT INTO grading_tasks(id,submission_id,class_id,user_id,max_attempts)
                   VALUES (?,?,?,?,?)""",
                task_rows,
            )
            db.commit()
        except BaseException:
            db.rollback()
            raise

    # Exercise the actual list endpoint once; the fixture itself has no result rows
    # and no outbox messages, so no grading worker or model can consume it.
    response = student.get("/api/tasks")
    require_status(response, 200, "list synthetic grading tasks")
    if len(response.json["tasks"]) != 50:
        raise RuntimeError("task list endpoint did not return its expected 50-row page")
    return assignment_id


def verify_real_http_audit(app, conversation_ids):
    from app.db import get_db

    with app.app_context():
        db = get_db()
        conversations = db.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event='http_request' AND json_extract(fields_json,'$.route')='/api/conversations'
                 AND json_extract(fields_json,'$.status')=201"""
        ).fetchone()[0]
        if conversations < len(conversation_ids):
            raise RuntimeError("conversation creation requests are missing from Flask audit events")
        route = "/api/conversations/<int:identifier>/messages"
        messages = db.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event='http_request' AND json_extract(fields_json,'$.route')=?
                 AND json_extract(fields_json,'$.status')=200""",
            (route,),
        ).fetchone()[0]
        if messages < len(conversation_ids):
            raise RuntimeError("expected successful message requests were not written by Flask audit hooks")
        agent_creates = db.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event='http_request' AND json_extract(fields_json,'$.route')='/api/agents'
                 AND json_extract(fields_json,'$.status')=201
                 AND json_extract(fields_json,'$.role')='teacher'"""
        ).fetchone()[0]
        if agent_creates < 2:
            raise RuntimeError("created agents are missing from Flask audit events")
        denied = db.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event='http_request' AND json_extract(fields_json,'$.route')='/api/agents'
                 AND json_extract(fields_json,'$.status')=403
                 AND json_extract(fields_json,'$.role')='student'"""
        ).fetchone()[0]
        if denied < 1:
            raise RuntimeError("student POST /api/agents did not produce an actual 403 audit event")
        total = db.execute("SELECT COUNT(*) FROM audit_events WHERE event='http_request'").fetchone()[0]
    print(
        f"http_audit_events={total}; conversation_create_201={conversations}; "
        f"completed_agent_questions={messages}; agent_create_201={agent_creates}; "
        f"student_agent_post_403={denied}",
        flush=True,
    )


def prepare(app):
    if app.extensions.get("week05_fixture", {}).get("mode") != "stub":
        raise RuntimeError("Week 5 factory did not report stub mode")
    if app.config.get("STREAM_PROVIDER") is None or app.config.get("VECTOR_STORE") is None:
        raise RuntimeError("local stub providers are required; refusing to start against a gateway")

    teacher = app.test_client()
    student = app.test_client()
    login(teacher, "teacher_a")
    login(student, "student_a1")

    skills, material_ids, seeded_agent_id = configure_skills(teacher, app)
    agents = configure_agents(teacher, skills, material_ids, seeded_agent_id)
    conversation_ids = [exercise_agent(student, item, agents[item["name"]]) for item in SKILLS]

    denied = student.post("/api/agents", json={
        "name": "学生越权创建应被拒绝",
        "role_prompt": "合成安全复测",
        "enabled": True,
        "skill_ids": [],
        "material_ids": [],
    })
    require_status(denied, 403, "student POST /api/agents")

    assignment_id = create_bench_fixture(app, teacher, student)
    verify_real_http_audit(app, conversation_ids)
    fixture = app.extensions["week05_fixture"]
    print(
        "fixture_mode=localstub "
        f"host={HOST} port={PORT} assignment_id={assignment_id} "
        f"synthetic_submission_tasks={BENCH_TASK_COUNT} "
        f"agents={','.join(item['agent'] for item in SKILLS)}",
        flush=True,
    )
    print("Synthetic local accounts (not production credentials):", flush=True)
    for username, password in ACCOUNTS.items():
        print(f"  {username} / {password}", flush=True)
    print(f"Fixture details: {json.dumps(fixture, ensure_ascii=False)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="new or empty directory for this local fixture")
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--fault-probe', action='store_true', help='explicit local fault provider for sustained alert verification')
    args = parser.parse_args()

    requested_dir = Path(args.data_dir).expanduser()
    if requested_dir.is_symlink():
        parser.error("--data-dir must not be a symlink")
    data_dir = requested_dir.resolve()
    if data_dir.exists():
        if not data_dir.is_dir():
            parser.error("--data-dir must name a directory")
        try:
            if next(data_dir.iterdir(), None) is not None:
                parser.error("--data-dir must be empty; existing evidence is never overwritten")
        except OSError as exc:
            parser.error(f"cannot inspect --data-dir: {exc}")

    app = make_week05_app(data_dir, stub=True)
    prepare(app)
    if not 1024 <= args.port <= 65535: parser.error('invalid local port')
    if args.fault_probe:
        normal = app.config['STREAM_PROVIDER']
        def controlled(messages):
            if '观测故障演练' in messages[-1]['content']:
                from app.gateway import GatewayUnavailable
                raise GatewayUnavailable('local controlled fault')
            yield from normal(messages)
        app.config['STREAM_PROVIDER'] = controlled
    print(f"Serving localstub evidence app at http://{HOST}:{PORT}/", flush=True)
    app.run(host=HOST, port=args.port, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
