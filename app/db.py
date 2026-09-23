import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS classes (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('teacher','student')),
  class_id INTEGER NOT NULL REFERENCES classes(id), password_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_class ON users(class_id);
CREATE TABLE IF NOT EXISTS lectures (
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id), title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id), title TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistants (
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id), name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skills (
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id), name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS materials (
  id INTEGER PRIMARY KEY, class_id INTEGER NOT NULL REFERENCES classes(id),
  teacher_id INTEGER REFERENCES users(id), title TEXT NOT NULL,
  stored_name TEXT, original_name TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_materials_class ON materials(class_id);
CREATE TABLE IF NOT EXISTS knowledge_entries (
  id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL UNIQUE REFERENCES materials(id),
  class_id INTEGER NOT NULL REFERENCES classes(id), body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_class ON knowledge_entries(class_id);
CREATE TABLE IF NOT EXISTS sessions (
  sid TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
  role TEXT NOT NULL, class_id INTEGER NOT NULL REFERENCES classes(id),
  expires_at TEXT NOT NULL
);
"""


def connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_PATH"])
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    path = Path(app.config["DATABASE_PATH"])
    if not path.exists():
        passwords = [
            app.config.get(key)
            for key in (
                "SEED_TEACHER_PASSWORD",
                "SEED_STUDENT_A_PASSWORD",
                "SEED_STUDENT_B_PASSWORD",
            )
        ]
        if any(not password for password in passwords):
            raise RuntimeError(
                "SEED_TEACHER_PASSWORD, SEED_STUDENT_A_PASSWORD and SEED_STUDENT_B_PASSWORD are required for first initialization"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        initialize(path, passwords)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)


def initialize(path, passwords):
    connection = connect(path)
    try:
        connection.executescript(SCHEMA)
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        with connection:
            connection.executemany(
                "INSERT OR IGNORE INTO classes(id,name) VALUES (?,?)",
                [(1, "A 班"), (2, "B 班")],
            )
            users = [
                ("teacher_a", "张老师", "teacher", 1, passwords[0]),
                ("student_a1", "A 班学生", "student", 1, passwords[1]),
                ("student_b1", "B 班学生", "student", 2, passwords[2]),
            ]
            for username, name, role, class_id, password in users:
                connection.execute(
                    "INSERT INTO users(username,display_name,role,class_id,password_hash) VALUES (?,?,?,?,?)",
                    (username, name, role, class_id, generate_password_hash(password)),
                )
            for class_id, title, body in [
                (1, "A 班入门讲义", "# A 班入门讲义\n\n本班材料示例。"),
                (2, "B 班实验说明", "# B 班实验说明\n\n仅 B 班可见。"),
            ]:
                material_id = connection.execute(
                    "INSERT INTO materials(class_id,title) VALUES (?,?)",
                    (class_id, title),
                ).lastrowid
                connection.execute(
                    "INSERT INTO knowledge_entries(material_id,class_id,body) VALUES (?,?,?)",
                    (material_id, class_id, body),
                )
    finally:
        connection.close()


def list_materials(class_id):
    return (
        get_db()
        .execute(
            "SELECT id,title,created_at FROM materials WHERE class_id=? ORDER BY id DESC",
            (class_id,),
        )
        .fetchall()
    )


def material_with_body(material_id):
    return (
        get_db()
        .execute(
            "SELECT m.*, k.body FROM materials m JOIN knowledge_entries k ON k.material_id=m.id WHERE m.id=?",
            (material_id,),
        )
        .fetchone()
    )
