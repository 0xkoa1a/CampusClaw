"""Exercise the deployed retrieval API using only the seeded synthetic corpus.

Run inside the app container after ``scripts.reindex_all``. Credentials are
read from the container environment and never printed or saved by this script.
"""

import http.cookiejar
import json
import os
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from app import create_app
from app.db import get_db
from app.vector import get_store


BASE = "http://127.0.0.1:8080"


class Client:
    def __init__(self):
        self.opener = build_opener(
            ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def post(self, path, payload, expected=200):
        request = Request(
            BASE + path,
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            response = self.opener.open(request, timeout=60)
        except HTTPError as error:
            response = error
        with response:
            body = json.load(response)
            assert response.status == expected, (path, response.status, expected)
            return body

    def get(self, path, expected=200):
        try:
            response = self.opener.open(BASE + path, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            assert response.status == expected, (path, response.status, expected)
            return body

    def login(self, username, password_key):
        assert self.post("/api/login", {
            "username": username, "password": os.environ[password_key]
        }) == {"ok": True}


def check_points():
    app = create_app()
    with app.app_context():
        rows = get_db().execute(
            "SELECT id,material_id,class_id,index_status FROM knowledge_chunks ORDER BY material_id"
        ).fetchall()
        expected = {row["id"]: row for row in rows}
        assert rows and all(row["index_status"] == "ready" for row in rows)
        store = get_store()
        response = store._request(
            "POST", store.path + "/points/scroll",
            {"limit": len(rows) + 10, "with_payload": True, "with_vector": False},
        )
        points = response["result"]["points"]
        assert response["result"].get("next_page_offset") is None
        assert {point["id"] for point in points} == set(expected)
        allowed = {"chunk_id", "material_id", "class_id", "knowledge_entry_id", "chunk_index"}
        for point in points:
            payload = point["payload"]
            row = expected[point["id"]]
            assert set(payload) == allowed
            assert payload["chunk_id"] == point["id"]
            assert payload["material_id"] == row["material_id"]
            assert payload["class_id"] == row["class_id"]
        return len(points)


def assert_synthetic_corpus():
    """Do not send any non-demo material to the external course gateway."""
    app = create_app()
    with app.app_context():
        rows = get_db().execute(
            """SELECT m.id,m.title,k.body FROM materials m
               JOIN knowledge_entries k ON k.material_id=m.id ORDER BY m.id"""
        ).fetchall()
    demos = {
        1: ("A 班入门讲义", "# A 班入门讲义\n\n本班材料示例。"),
        2: ("B 班实验说明", "# B 班实验说明\n\n仅 B 班可见。"),
    }
    acceptance_body = "# Compose persistence check\n\n班级 A 的容器重建验收材料。"
    assert len(rows) >= 2, "只允许在合成验收材料库运行"
    for row in rows:
        if row["id"] in demos:
            assert (row["title"], row["body"]) == demos[row["id"]], "只允许在合成验收材料库运行"
        else:
            assert row["title"].startswith("compose-check-") and row["body"] == acceptance_body, "只允许在合成验收材料库运行"


def main():
    assert_synthetic_corpus()
    anonymous, teacher, student_a, student_b = (Client() for _ in range(4))
    anonymous.post("/api/search", {"q": "入门"}, 401)
    teacher.login("teacher_a", "SEED_TEACHER_PASSWORD")
    student_a.login("student_a1", "SEED_STUDENT_A_PASSWORD")
    student_b.login("student_b1", "SEED_STUDENT_B_PASSWORD")

    keyword = student_a.post("/api/search", {"q": "入门", "mode": "keyword"})
    assert any(hit["material_id"] == 1 for hit in keyword["hits"])
    assert student_b.post("/api/search?class_id=1", {
        "q": "入门", "mode": "keyword", "class_id": 1,
    })["hits"] == []
    for mode in ("vector", "hybrid"):
        result = student_a.post("/api/search", {"q": "入门", "mode": mode})
        assert any(hit["material_id"] == 1 for hit in result["hits"]), mode
        assert all(hit["material_id"] != 2 for hit in result["hits"]), mode
        assert all(hit["source_url"].startswith("/materials?id=") for hit in result["hits"])

    source = keyword["hits"][0]["source_url"]
    assert b'<mark id="source">' in student_a.get(source)
    student_b.get(source, 404)
    answer = student_a.post("/api/ask", {"q": "A 班入门讲义中有什么示例？"})
    assert answer["answer"].strip()
    assert answer["citations"]
    assert all(item["material_id"] != 2 for item in answer["citations"])
    for citation in answer["citations"]:
        assert f"[{citation['number']}]" in answer["answer"]
        student_a.get(citation["source_url"])

    student_a.post("/api/materials/1/reindex", {}, 403)
    teacher.post("/api/materials/2/reindex", {}, 404)
    point_count = check_points()
    print(json.dumps({"result": "PASS", "keyword": True, "vector": True,
                      "hybrid": True, "answer_citations": len(answer["citations"]),
                      "qdrant_points": point_count, "class_boundary": True,
                      "source_highlight": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
