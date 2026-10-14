import pytest

from app.agent_store import ApiProblem, parse_skill
from app.db import connect, initialize, migrate
from conftest import login


def skill_source(name="演示技能", *, trigger="测试关键词", subject="", tool="knowledge_search", enabled="是", body="只回答当前问题。"):
    return (
        f"名称：{name}\n适用条件：{trigger}\n资料：{subject}\n"
        f"工具：{tool}\n启用：{enabled}\n\n{body}"
    )


def create_skill(client, source=None):
    return client.post("/api/skills", json={"source": source or skill_source()})


def create_agent(client, *, name="演示智能体", prompt="回答问题", enabled=True, skill_ids=None, material_ids=None):
    return client.post("/api/agents", json={
        "name": name,
        "role_prompt": prompt,
        "enabled": enabled,
        "skill_ids": skill_ids or [],
        "material_ids": material_ids or [],
    })


def test_parse_skill_valid_source():
    source = skill_source("线性代数", trigger="矩阵,向量", subject="数学", body="先解释概念，再给例子。")

    parsed = parse_skill(source)

    assert parsed["name"] == "线性代数"
    assert parsed["trigger_text"] == "矩阵,向量"
    assert parsed["subject_text"] == "数学"
    assert parsed["description"] == "先解释概念，再给例子。"
    assert parsed["tools_json"] == '["knowledge_search"]'
    assert parsed["enabled"] is True
    assert parsed["source_text"] == source


@pytest.mark.parametrize("source", [
    "名称：重复字段\n名称：再来一次\n适用条件：关键词\n启用：是\n\n正文",
    "名称：未知字段\n适用条件：关键词\n未知：不支持\n启用：是\n\n正文",
    skill_source("名" * 33),
    skill_source("长度测试", trigger="触发" * 61),
    skill_source("长度测试", subject="科目" * 17),
    skill_source("长度测试", body="正文" * 1001),
    skill_source("长度测试", tool="knowledge_search,web_search"),
    skill_source("长度测试", body=" \n  "),
    "名称：空启用\n适用条件：关键词\n启用：是\n\n   ",
])
def test_parse_skill_rejects_duplicate_unknown_oversize_tool_and_empty_body(source):
    with pytest.raises(ApiProblem):
        parse_skill(source)


def test_parse_skill_rejects_source_overall_limit():
    with pytest.raises(ApiProblem):
        parse_skill("x" * 8001)


def test_teacher_skill_crud_and_unique_name(client):
    login(client)
    created = create_skill(client, skill_source("唯一技能"))
    assert created.status_code == 201
    skill_id = created.json["skill"]["id"]
    assert created.json["skill"]["enabled"] is True

    duplicate = create_skill(client, skill_source("唯一技能", body="不同正文"))
    assert duplicate.status_code == 400

    updated_source = skill_source("唯一技能", trigger="更新后的关键词", body="更新后的正文。")
    updated = client.put(f"/api/skills/{skill_id}", json={"source": updated_source})
    assert updated.status_code == 200
    assert updated.json["skill"]["source_text"] == updated_source
    assert updated.json["skill"]["trigger_text"] == "更新后的关键词"

    deleted = client.delete(f"/api/skills/{skill_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/skills/{skill_id}").status_code == 404


def test_teacher_agent_crud_unique_name_and_students_see_enabled_only(client):
    login(client)
    enabled = create_agent(client, name="已启用智能体")
    disabled = create_agent(client, name="已停用智能体", enabled=False)
    assert enabled.status_code == 201 and disabled.status_code == 201
    agent_id = enabled.json["agent"]["id"]

    duplicate = create_agent(client, name="已启用智能体", prompt="重名")
    assert duplicate.status_code == 400

    updated = client.put(f"/api/agents/{agent_id}", json={
        "name": "已启用智能体", "role_prompt": "更新后的提示词", "enabled": True,
        "skill_ids": [], "material_ids": [],
    })
    assert updated.status_code == 200
    assert updated.json["agent"]["role_prompt"] == "更新后的提示词"

    login(client, "student_a1", "student-a-test-password")
    listing = client.get("/api/agents")
    assert listing.status_code == 200
    ids = {agent["id"] for agent in listing.json["agents"]}
    assert agent_id in ids
    assert disabled.json["agent"]["id"] not in ids
    assert client.get(f"/api/agents/{disabled.json['agent']['id']}").status_code == 404


def test_students_cannot_write_skills_or_agents(client):
    login(client)
    skill_id = create_skill(client).json["skill"]["id"]
    agent_id = create_agent(client).json["agent"]["id"]
    login(client, "student_a1", "student-a-test-password")

    assert create_skill(client, skill_source("学生尝试写入")).status_code == 403
    assert client.put(f"/api/skills/{skill_id}", json={"source": skill_source("学生更新")}).status_code == 403
    assert client.delete(f"/api/skills/{skill_id}").status_code == 403
    assert create_agent(client, name="学生尝试创建").status_code == 403
    assert client.put(f"/api/agents/{agent_id}", json={
        "name": "学生尝试更新", "role_prompt": "越权", "enabled": True,
        "skill_ids": [], "material_ids": [],
    }).status_code == 403


def test_teacher_resources_from_another_class_return_404(client, app):
    login(client)
    skill_id = create_skill(client).json["skill"]["id"]
    agent_id = create_agent(client).json["agent"]["id"]
    connection = connect(app.config["DATABASE_PATH"])
    try:
        with connection:
            other_skill_id = connection.execute(
                "INSERT INTO skills(class_id,name,source_text,enabled) VALUES (2,?,?,1)",
                ("B班专属技能", "B班内容"),
            ).lastrowid
    finally:
        connection.close()

    assert client.get(f"/api/skills/{other_skill_id}").status_code == 404
    assert client.put(f"/api/skills/{other_skill_id}", json={"source": skill_source("跨班更新")}).status_code == 404
    assert client.get(f"/api/agents/{agent_id + 100000}").status_code == 404
    login(client, "student_b1", "student-b-test-password")
    assert client.get(f"/api/agents/{agent_id}").status_code == 404
    assert client.get(f"/api/skills/{skill_id}").status_code == 404


def test_cross_class_agent_binding_rejected_without_changing_existing_configuration(client, app):
    login(client)
    own_skill_id = create_skill(client, skill_source("A班技能")).json["skill"]["id"]
    agent = create_agent(client, name="原配置", prompt="保留的提示", skill_ids=[own_skill_id], material_ids=[1])
    assert agent.status_code == 201
    agent_id = agent.json["agent"]["id"]

    connection = connect(app.config["DATABASE_PATH"])
    try:
        with connection:
            other_skill_id = connection.execute(
                "INSERT INTO skills(class_id,name,source_text,enabled) VALUES (2,?,?,1)",
                ("B班不可绑定技能", "不得改变"),
            ).lastrowid
    finally:
        connection.close()

    rejected = client.put(f"/api/agents/{agent_id}", json={
        "name": "被拒绝的改名", "role_prompt": "不应保存", "enabled": False,
        "skill_ids": [other_skill_id], "material_ids": [2],
    })
    assert rejected.status_code == 404

    unchanged = client.get(f"/api/agents/{agent_id}").json["agent"]
    assert unchanged["name"] == "原配置"
    assert unchanged["role_prompt"] == "保留的提示"
    assert unchanged["enabled"] is True
    assert unchanged["skill_ids"] == [own_skill_id]
    assert unchanged["material_ids"] == [1]


def test_deleting_skill_cascades_agent_binding(client, app):
    login(client)
    skill_id = create_skill(client, skill_source("绑定后删除")).json["skill"]["id"]
    agent_id = create_agent(client, skill_ids=[skill_id]).json["agent"]["id"]

    response = client.delete(f"/api/skills/{skill_id}")
    assert response.status_code == 204
    connection = connect(app.config["DATABASE_PATH"])
    try:
        assert connection.execute("SELECT 1 FROM skills WHERE id=?", (skill_id,)).fetchone() is None
        assert connection.execute("SELECT 1 FROM agent_skills WHERE agent_id=? AND skill_id=?", (agent_id, skill_id)).fetchone() is None
    finally:
        connection.close()


def _seed_legacy_database(path):
    passwords = ["teacher-legacy-password", "student-a-legacy-password", "student-b-legacy-password"]
    initialize(path, passwords)
    connection = connect(path)
    try:
        with connection:
            skill_id = connection.execute(
                "INSERT INTO skills(class_id,name) VALUES (1,?)", ("旧技能",)
            ).lastrowid
        snapshot = {
            "skill_id": skill_id,
            "users": [tuple(row) for row in connection.execute(
                "SELECT id,username,role,class_id,password_hash FROM users ORDER BY id"
            )],
            "material": tuple(connection.execute(
                "SELECT m.id,m.title,k.body FROM materials m JOIN knowledge_entries k ON k.material_id=m.id ORDER BY m.id LIMIT 1"
            ).fetchone()),
        }
        return snapshot
    finally:
        connection.close()


def test_migration_is_idempotent_and_preserves_legacy_ids_material_text_and_accounts(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    before = _seed_legacy_database(path)

    migrate(path)
    connection = connect(path)
    try:
        legacy = connection.execute("SELECT * FROM skills WHERE id=?", (before["skill_id"],)).fetchone()
        assert legacy["name"] == "旧技能"
        assert legacy["enabled"] == 0
        assert legacy["source_text"] == ""
        once = {
            "skills": [tuple(row) for row in connection.execute("SELECT * FROM skills ORDER BY id")],
            "agents": connection.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
            "users": [tuple(row) for row in connection.execute(
                "SELECT id,username,role,class_id,password_hash FROM users ORDER BY id"
            )],
            "material": tuple(connection.execute(
                "SELECT m.id,m.title,k.body FROM materials m JOIN knowledge_entries k ON k.material_id=m.id ORDER BY m.id LIMIT 1"
            ).fetchone()),
        }
    finally:
        connection.close()

    migrate(path)
    connection = connect(path)
    try:
        twice = {
            "skills": [tuple(row) for row in connection.execute("SELECT * FROM skills ORDER BY id")],
            "agents": connection.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
            "users": [tuple(row) for row in connection.execute(
                "SELECT id,username,role,class_id,password_hash FROM users ORDER BY id"
            )],
            "material": tuple(connection.execute(
                "SELECT m.id,m.title,k.body FROM materials m JOIN knowledge_entries k ON k.material_id=m.id ORDER BY m.id LIMIT 1"
            ).fetchone()),
        }
    finally:
        connection.close()

    assert twice == once
    assert once["users"] == before["users"]
    assert once["material"] == before["material"]


def test_migration_rejects_duplicate_legacy_skill_names(tmp_path):
    path = tmp_path / "duplicate-skills.sqlite3"
    _seed_legacy_database(path)
    connection = connect(path)
    try:
        with connection:
            connection.executemany(
                "INSERT INTO skills(class_id,name) VALUES (1,?)",
                [("重复旧技能",), ("重复旧技能",)],
            )
    finally:
        connection.close()

    with pytest.raises(RuntimeError, match="技能班内名称重复"):
        migrate(path)

    connection = connect(path)
    try:
        duplicates = connection.execute(
            "SELECT COUNT(*) FROM skills WHERE class_id=1 AND name='重复旧技能'"
        ).fetchone()[0]
        columns = {row[1] for row in connection.execute("PRAGMA table_info(skills)")}
    finally:
        connection.close()
    assert duplicates == 2
    assert "source_text" not in columns
