import io
import sqlite3
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

from app import create_app
from app.db import connect, initialize
from conftest import login


def upload(client, filename="lesson.md", body=b"# Lesson\n\nHello class A", **fields):
    return client.post(
        "/api/materials", data={"file": (io.BytesIO(body), filename), **fields}
    )


def counts(app):
    connection = connect(app.config["DATABASE_PATH"])
    try:
        return tuple(
            connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in ("materials", "knowledge_entries")
        )
    finally:
        connection.close()


def files(app):
    return sorted(
        path for path in Path(app.config["UPLOAD_DIR"]).rglob("*") if path.is_file()
    )


def test_schema_seed_and_hashes(app):
    connection = connect(app.config["DATABASE_PATH"])
    try:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "classes",
            "users",
            "lectures",
            "assignments",
            "assistants",
            "skills",
            "materials",
            "knowledge_entries",
            "sessions",
        } <= names
        users = connection.execute(
            "SELECT username,role,class_id,password_hash FROM users ORDER BY id"
        ).fetchall()
        assert [(u["username"], u["role"], u["class_id"]) for u in users] == [
            ("teacher_a", "teacher", 1),
            ("student_a1", "student", 1),
            ("student_b1", "student", 2),
        ]
        assert check_password_hash(users[0]["password_hash"], "teacher-test-password")
        assert "teacher-test-password" not in users[0]["password_hash"]
        assert counts(app) == (2, 2)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO materials(class_id,title) VALUES (NULL,'bad')"
            )
    finally:
        connection.close()


def test_initialize_is_idempotent(app):
    path = app.config["DATABASE_PATH"]
    initialize(path, ["ignored", "ignored", "ignored"])
    assert counts(app) == (2, 2)
    connection = connect(path)
    try:
        user = connection.execute(
            "SELECT password_hash FROM users WHERE username='teacher_a'"
        ).fetchone()
        assert check_password_hash(user[0], "teacher-test-password")
    finally:
        connection.close()


def test_missing_secret_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"DATABASE_PATH": str(tmp_path / "db.sqlite3")})


def test_health_and_anonymous_rejected(client):
    assert client.get("/health").json == {"status": "ok"}
    assert client.get("/materials").status_code == 302
    for url in (
        "/api/me",
        "/api/materials",
        "/api/materials/1",
        "/api/materials/1/file",
    ):
        response = client.get(url)
        assert response.status_code == 401
        assert "A 班入门讲义" not in response.get_data(as_text=True)


def test_database_failure_is_service_unavailable_not_logout(app, client):
    login(client)
    connection = connect(app.config["DATABASE_PATH"])
    try:
        connection.execute("DROP TABLE sessions")
        connection.commit()
    finally:
        connection.close()
    assert client.get("/health").json == {"status": "ok"}
    response = client.get("/api/materials")
    assert response.status_code == 503
    assert "请先登录" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "username,password,role,class_id",
    [
        ("teacher_a", "teacher-test-password", "teacher", 1),
        ("student_a1", "student-a-test-password", "student", 1),
        ("student_b1", "student-b-test-password", "student", 2),
    ],
)
def test_login_and_me(client, username, password, role, class_id):
    assert login(client, username, password).status_code == 200
    me = client.get("/api/me").json
    assert (me["role"], me["class_id"]) == (role, class_id)


def test_bad_login_same_response_and_no_session(client):
    wrong = login(client, "teacher_a", "wrong")
    unknown = login(client, "nobody", "wrong")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json == unknown.json
    assert client.get("/api/me").status_code == 401
    assert "password_hash" not in wrong.get_data(as_text=True)


def test_logout_revokes_old_cookie(app):
    client = app.test_client()
    assert login(client).status_code == 200
    cookie = client.get_cookie("session")
    assert cookie is not None
    assert client.post("/api/logout").status_code == 200
    client.set_cookie("session", cookie.value)
    assert client.get("/api/materials").status_code == 401


def test_class_isolation_and_tampering(client):
    assert login(client, "student_a1", "student-a-test-password").status_code == 200
    response = client.get("/api/materials?class_id=2", headers={"X-Class-Id": "2"})
    assert response.status_code == 200
    assert [m["title"] for m in response.json["materials"]] == ["A 班入门讲义"]
    assert client.get("/api/materials/1").json["body"].startswith("# A 班")
    cross = client.get("/api/materials/2")
    missing = client.get("/api/materials/9999")
    assert cross.status_code == missing.status_code == 404
    assert cross.json == missing.json
    assert "B 班" not in cross.get_data(as_text=True)
    assert (
        client.get("/api/materials/2/file").json
        == client.get("/api/materials/9999/file").json
    )
    page_cross = client.get("/materials?id=2")
    page_missing = client.get("/materials?id=9999")
    assert page_cross.status_code == page_missing.status_code == 404
    assert "B 班实验说明" not in page_cross.get_data(as_text=True)


def test_student_upload_rejected_without_side_effects(app, client):
    login(client, "student_a1", "student-a-test-password")
    before = counts(app)
    assert upload(client).status_code == 403
    assert counts(app) == before
    assert files(app) == []


def test_teacher_upload_visible_to_own_class_and_download(app):
    teacher = app.test_client()
    student_a = app.test_client()
    student_b = app.test_client()
    login(teacher)
    response = upload(
        teacher, "new.md", b"# New\n\nA only", class_id="2", role="student"
    )
    assert response.status_code == 201
    material_id = response.json["id"]
    assert counts(app) == (3, 3)
    detail = teacher.get(f"/api/materials/{material_id}").json
    assert detail["class_id"] == 1 and detail["body"] == "# New\n\nA only"
    assert "new.md" in teacher.get("/materials").get_data(as_text=True)
    assert teacher.get(f"/api/materials/{material_id}/file").data == b"# New\n\nA only"
    assert len(files(app)) == 1
    assert files(app)[0].name != "new.md"
    login(student_a, "student_a1", "student-a-test-password")
    assert any(
        m["title"] == "new.md"
        for m in student_a.get("/api/materials").json["materials"]
    )
    assert student_a.get(f"/api/materials/{material_id}/file").status_code == 200
    login(student_b, "student_b1", "student-b-test-password")
    assert "new.md" not in student_b.get("/api/materials").get_data(as_text=True)
    assert student_b.get(f"/api/materials/{material_id}").status_code == 404
    assert student_b.get(f"/api/materials/{material_id}/file").status_code == 404


@pytest.mark.parametrize(
    "filename,body,status",
    [
        ("evil.exe", b"hello", 400),
        ("evil.md.exe", b"hello", 400),
        ("empty.md", b"", 400),
        ("blank.txt", b"  \n", 400),
        ("broken.md", b"\xff\xfe", 400),
        ("huge.md", b"x" * 1025, 413),
    ],
)
def test_invalid_upload_leaves_no_data(app, client, filename, body, status):
    login(client)
    before = counts(app)
    assert upload(client, filename, body).status_code == status
    assert counts(app) == before
    assert files(app) == []


def test_database_failure_rolls_back_and_removes_file(app, client):
    login(client)
    connection = connect(app.config["DATABASE_PATH"])
    try:
        connection.execute(
            "CREATE TRIGGER fail_knowledge BEFORE INSERT ON knowledge_entries "
            "BEGIN SELECT RAISE(FAIL, 'injected failure'); END"
        )
        connection.commit()
    finally:
        connection.close()
    assert upload(client).status_code == 500
    assert counts(app) == (2, 2)
    assert files(app) == []


def test_filename_cannot_escape_upload_directory_and_html_is_escaped(app, client):
    login(client)
    response = upload(client, "../unsafe.md", b"<script>alert(1)</script>")
    assert response.status_code == 201
    material_id = response.json["id"]
    saved = files(app)
    assert len(saved) == 1
    assert saved[0].parent == Path(app.config["UPLOAD_DIR"]) / "1"
    html = client.get(f"/materials?id={material_id}").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_restart_preserves_uploaded_data(app, client):
    login(client)
    material_id = upload(client).json["id"]
    second = create_app(
        {
            **{
                key: app.config[key]
                for key in (
                    "SECRET_KEY",
                    "DATABASE_PATH",
                    "UPLOAD_DIR",
                    "MAX_UPLOAD_BYTES",
                    "SEED_TEACHER_PASSWORD",
                    "SEED_STUDENT_A_PASSWORD",
                    "SEED_STUDENT_B_PASSWORD",
                )
            },
            "TESTING": True,
        }
    )
    second_client = second.test_client()
    login(second_client, "student_a1", "student-a-test-password")
    assert second_client.get(f"/api/materials/{material_id}").status_code == 200
    assert counts(second) == (3, 3)
