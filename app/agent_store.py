"""Class-scoped agent configuration and the course's plain-text skill format."""

import json
import re
import sqlite3

from .db import get_db


class ApiProblem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def missing():
    return ApiProblem("资源不存在", 404)


def migrate_week05(connection):
    duplicates = connection.execute(
        "SELECT 1 FROM skills GROUP BY class_id,name HAVING COUNT(*)>1 LIMIT 1"
    ).fetchone()
    if duplicates:
        raise RuntimeError("技能班内名称重复，请先人工核对；迁移未删除任何数据")
    additions = {
        "source_text": "TEXT NOT NULL DEFAULT ''", "trigger_text": "TEXT NOT NULL DEFAULT ''",
        "description": "TEXT NOT NULL DEFAULT ''", "subject_text": "TEXT NOT NULL DEFAULT ''",
        "tools_json": "TEXT NOT NULL DEFAULT '[]'", "enabled": "INTEGER NOT NULL DEFAULT 0",
    }
    statements = [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_class_name ON skills(class_id,name)",
        """CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id),
            name TEXT NOT NULL, role_prompt TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
            UNIQUE(class_id,name))""",
        """CREATE TABLE IF NOT EXISTS agent_skills (
            agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
            PRIMARY KEY(agent_id,skill_id))""",
        """CREATE TABLE IF NOT EXISTS agent_materials (
            agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            material_id INTEGER NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            PRIMARY KEY(agent_id,material_id))""",
        """CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id),
            user_id INTEGER NOT NULL REFERENCES users(id), agent_id INTEGER NOT NULL REFERENCES agents(id),
            title TEXT NOT NULL DEFAULT '新的提问',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        "CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations(user_id,class_id,updated_at)",
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
            citations_json TEXT NOT NULL DEFAULT '[]', skill_name TEXT,
            status TEXT NOT NULL DEFAULT 'complete' CHECK(status IN ('complete','partial')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id,id)",
    ]
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(skills)")}
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE skills ADD COLUMN {name} {definition}")
        for statement in statements:
            connection.execute(statement)


def parse_skill(source):
    if not isinstance(source, str) or len(source) > 8000:
        raise ApiProblem("技能文件必须是最多8000字的文本")
    text = source.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    header, separator, body = text.partition("\n\n")
    if not separator or not body.strip():
        raise ApiProblem("字段后需要空行和非空规程正文")
    fields = {}
    for line in header.splitlines():
        if line.lstrip().startswith("#"):
            continue
        parts = re.split("[：:]", line, maxsplit=1)
        if len(parts) != 2:
            raise ApiProblem("字段须使用 名称：内容 的格式")
        key, value = (part.strip() for part in parts)
        if key not in {"名称", "适用条件", "资料", "工具", "启用"} or key in fields:
            raise ApiProblem("存在未知或重复字段")
        fields[key] = value
    if any(not fields.get(key) for key in ("名称", "适用条件", "启用")):
        raise ApiProblem("名称、适用条件、启用为必填字段")
    if fields["启用"] not in {"是", "否"}:
        raise ApiProblem("启用须为 是 或 否")
    limits = {"名称": 32, "适用条件": 120, "资料": 32}
    if any(len(fields.get(key, "")) > limit for key, limit in limits.items()) or len(body.strip()) > 2000:
        raise ApiProblem("技能字段或正文超过长度限制")
    tools = [x.strip() for x in re.split(r"[,，、;；|]", fields.get("工具", "")) if x.strip()]
    if any(tool not in {"knowledge_search", "calculator"} and not re.fullmatch(r"[a-z][a-z0-9_]*@[a-z][a-z0-9-]*", tool) for tool in tools):
        raise ApiProblem("工具须为 knowledge_search、calculator 或 工具名@服务器名")
    return dict(name=fields["名称"], trigger_text=fields["适用条件"],
                subject_text=fields.get("资料", ""), description=body.strip(),
                enabled=fields["启用"] == "是", tools_json=json.dumps(tools), source_text=source)


def skill_json(row):
    item = dict(row)
    item["enabled"] = bool(item["enabled"])
    item["tools"] = json.loads(item.pop("tools_json"))
    return item


def agent_json(row):
    item = dict(row)
    item["tool_names"] = json.loads(item.pop("tool_names_json", "[]"))
    item["enabled"] = bool(item["enabled"])
    db = get_db()
    item["skill_ids"] = [r[0] for r in db.execute("SELECT skill_id FROM agent_skills WHERE agent_id=? ORDER BY skill_id", (row["id"],))]
    item["material_ids"] = [r[0] for r in db.execute("SELECT material_id FROM agent_materials WHERE agent_id=? ORDER BY material_id", (row["id"],))]
    return item


def owned_row(table, identifier, class_id):
    if table not in {"agents", "skills"}:
        raise ValueError("unsupported resource")
    row = get_db().execute(f"SELECT * FROM {table} WHERE id=? AND class_id=?", (identifier, class_id)).fetchone()
    if row is None:
        raise missing()
    return row


def save_skill(class_id, source, identifier=None):
    item = parse_skill(source)
    from .mcp_registry import validate_references
    validate_references(json.loads(item["tools_json"]), class_id)
    db = get_db()
    if identifier is not None:
        owned_row("skills", identifier, class_id)
    try:
        with db:
            if identifier is None:
                identifier = db.execute(
                    "INSERT INTO skills(class_id,name,trigger_text,description,subject_text,tools_json,source_text,enabled) VALUES (?,?,?,?,?,?,?,?)",
                    (class_id, *(item[k] for k in ("name", "trigger_text", "description", "subject_text", "tools_json", "source_text", "enabled"))),
                ).lastrowid
            else:
                db.execute("UPDATE skills SET name=?,trigger_text=?,description=?,subject_text=?,tools_json=?,source_text=?,enabled=? WHERE id=? AND class_id=?",
                           (*(item[k] for k in ("name", "trigger_text", "description", "subject_text", "tools_json", "source_text", "enabled")), identifier, class_id))
    except sqlite3.IntegrityError as exc:
        raise ApiProblem("本班已存在同名技能") from exc
    return skill_json(owned_row("skills", identifier, class_id))


def save_agent(class_id, payload, identifier=None):
    if not isinstance(payload, dict):
        raise ApiProblem("需要JSON对象")
    current = agent_json(owned_row("agents", identifier, class_id)) if identifier is not None else {}
    data = {**current, **payload}
    tool_names = data.get("tool_names", [])
    from .platform_tools import TOOL_NAMES
    if not isinstance(tool_names, list) or any(not isinstance(name, str) or name not in TOOL_NAMES for name in tool_names):
        raise ApiProblem("tool_names须为允许的工具名称数组")
    tool_names = sorted(set(tool_names))
    name, prompt, enabled = data.get("name"), data.get("role_prompt", ""), data.get("enabled", True)
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 64:
        raise ApiProblem("智能体名称须为1–64字")
    if not isinstance(prompt, str) or len(prompt) > 2000 or type(enabled) is not bool:
        raise ApiProblem("提示词最多2000字，enabled须为布尔值")
    bindings = {}
    db = get_db()
    for key, table in (("skill_ids", "skills"), ("material_ids", "materials")):
        values = data.get(key, [])
        if not isinstance(values, list) or any(type(i) is not int or i <= 0 for i in values):
            raise ApiProblem("绑定编号须为正整数数组")
        bindings[key] = sorted(set(values))
        for value in bindings[key]:
            if not db.execute(f"SELECT 1 FROM {table} WHERE id=? AND class_id=?", (value, class_id)).fetchone():
                raise missing()
    try:
        with db:
            if identifier is None:
                identifier = db.execute("INSERT INTO agents(class_id,name,role_prompt,enabled) VALUES (?,?,?,?)", (class_id, name.strip(), prompt, enabled)).lastrowid
            else:
                db.execute("UPDATE agents SET name=?,role_prompt=?,enabled=? WHERE id=? AND class_id=?", (name.strip(), prompt, enabled, identifier, class_id))
            for table, column, key in (("agent_skills", "skill_id", "skill_ids"), ("agent_materials", "material_id", "material_ids")):
                db.execute(f"DELETE FROM {table} WHERE agent_id=?", (identifier,))
                db.executemany(f"INSERT INTO {table}(agent_id,{column}) VALUES (?,?)", [(identifier, value) for value in bindings[key]])
            db.execute("UPDATE agents SET tool_names_json=? WHERE id=?", (json.dumps(tool_names), identifier))
    except sqlite3.IntegrityError as exc:
        raise ApiProblem("本班已存在同名智能体或绑定资源已改变") from exc
    return agent_json(owned_row("agents", identifier, class_id))


def select_skill(agent_id, class_id, question):
    rows = get_db().execute("SELECT s.* FROM skills s JOIN agent_skills b ON s.id=b.skill_id WHERE b.agent_id=? AND s.class_id=? AND s.enabled=1 ORDER BY s.id", (agent_id, class_id)).fetchall()
    selected, score = None, 0
    for row in rows:
        words = [w.strip().lower() for w in re.split(r"[,，、;；|]", row["trigger_text"]) if w.strip()]
        hits = sum(word in question.lower() for word in words)
        if hits > score:
            selected, score = row, hits
    return selected
