"""Run inside the app container, before and after Compose down/up.

The before phase uploads one synthetic Markdown material. Both phases read
credentials from the container environment; no passwords or cookies are saved.
"""

import argparse
import hashlib
import http.cookiejar
import json
import os
import sqlite3
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener


BASE = "http://127.0.0.1:8080"


class Client:
    def __init__(self):
        self.opener = build_opener(
            ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def request(self, path, expected=200, data=None, content_type="application/json"):
        headers = {"Content-Type": content_type} if data is not None else {}
        try:
            response = self.opener.open(Request(BASE + path, data, headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == expected, (path, response.status, expected)
        return body

    def login(self, username, env_key):
        self.request("/api/login", data=json.dumps({
            "username": username, "password": os.environ[env_key]
        }).encode())

    def upload(self, title, body, expected):
        boundary = uuid.uuid4().hex
        data = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="class_id"\r\n\r\n2\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{title}"\r\n'
            f'Content-Type: text/markdown\r\n\r\n{body}\r\n--{boundary}--\r\n'
        ).encode()
        return self.request("/api/materials", expected, data,
                            f"multipart/form-data; boundary={boundary}")


def snapshot():
    with sqlite3.connect(os.environ["DATABASE_PATH"]) as db:
        counts = [db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("users", "materials", "knowledge_entries")]
    files = sorted(str(path.relative_to(os.environ["UPLOAD_DIR"]))
                   for path in Path(os.environ["UPLOAD_DIR"]).rglob("*") if path.is_file())
    return {"counts": counts, "files": files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before", "after"))
    args = parser.parse_args()
    state_path = Path(os.environ["DATABASE_PATH"]).parent / "verification.json"
    anon, teacher, student, other = (Client() for _ in range(4))
    assert json.loads(anon.request("/health")) == {"status": "ok"}
    anon.request("/login")
    anon.request("/api/materials", 401)
    for client, username, key, role, class_id in (
        (teacher, "teacher_a", "SEED_TEACHER_PASSWORD", "teacher", 1),
        (student, "student_a1", "SEED_STUDENT_A_PASSWORD", "student", 1),
        (other, "student_b1", "SEED_STUDENT_B_PASSWORD", "student", 2),
    ):
        client.login(username, key)
        me = json.loads(client.request("/api/me"))
        assert (me["role"], me["class_id"]) == (role, class_id)

    initial = snapshot()
    student.upload("forbidden.md", "student must not write", 403)
    teacher.upload("invalid.pdf", "invalid format", 400)
    assert snapshot() == initial, "Rejected uploads changed persistent state"
    for client in (teacher, student):
        for suffix in ("", "/file"):
            assert client.request("/api/materials/2" + suffix, 404) == client.request(
                "/api/materials/999999999" + suffix, 404)
        client.request("/materials?id=2", 404)

    if args.phase == "before":
        title = f"compose-check-{uuid.uuid4().hex[:8]}.md"
        body = "# Compose persistence check\n\n班级 A 的容器重建验收材料。"
        material_id = json.loads(teacher.upload(title, body, 201))["id"]
        state = {"id": material_id, "title": title, "body": body}
        state["sha256"] = hashlib.sha256(body.encode()).hexdigest()
        state["snapshot"] = snapshot()
        assert state["snapshot"]["counts"] == [initial["counts"][0],
                                                initial["counts"][1] + 1,
                                                initial["counts"][2] + 1]
        assert len(state["snapshot"]["files"]) == len(initial["files"]) + 1
    else:
        state = json.loads(state_path.read_text())
        assert snapshot() == state["snapshot"], "Persistent state changed after recreation"

    path = f'/api/materials/{state["id"]}'
    for client in (teacher, student):
        rows = json.loads(client.request("/api/materials?class_id=2"))["materials"]
        assert any(row["id"] == state["id"] for row in rows)
        assert all(row["id"] != 2 for row in rows)
        detail = json.loads(client.request(path))
        assert (detail["class_id"], detail["title"], detail["body"]) == (
            1, state["title"], state["body"])
        assert hashlib.sha256(client.request(path + "/file")).hexdigest() == state["sha256"]
    other.request(path, 404)
    other.request(path + "/file", 404)
    assert all(row["id"] != state["id"] for row in
               json.loads(other.request("/api/materials"))["materials"])
    with sqlite3.connect(os.environ["DATABASE_PATH"]) as db:
        row = db.execute(
            "SELECT m.class_id,k.class_id,k.body FROM materials m JOIN knowledge_entries k "
            "ON m.id=k.material_id WHERE m.id=?", (state["id"],)
        ).fetchone()
        assert row == (1, 1, state["body"])
    teacher.request("/api/logout", data=b"{}")
    teacher.request("/api/me", 401)
    if args.phase == "before":
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": args.phase, "result": "PASS", "material_id": state["id"],
                      "sha256": state["sha256"], **snapshot()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
