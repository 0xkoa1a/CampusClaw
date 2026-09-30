import io
import math

from app import create_app
from app.chunking import split_text
from app.db import get_db, initialize
from app.gateway import GatewayUnavailable
from app.indexing import index_material
from app.vector import VectorUnavailable
from conftest import login


class FakeStore:
    def __init__(self):
        self.points = {}
        self.unavailable = False

    def upsert(self, points):
        for point in points:
            self.points[point["id"]] = point

    def delete(self, ids):
        for identifier in ids:
            self.points.pop(identifier, None)

    def query(self, vector, class_id, limit):
        if self.unavailable:
            raise VectorUnavailable("向量服务暂时不可用")
        result = []
        for point in self.points.values():
            if point["payload"]["class_id"] != class_id:
                continue
            a, b = point["vector"], vector
            score = sum(x * y for x, y in zip(a, b)) / (math.dist(a, [0] * len(a)) * math.dist(b, [0] * len(b)))
            if score >= 0.35:
                result.append({"id": point["id"], "payload": point["payload"], "score": score})
        return sorted(result, key=lambda item: -item["score"])[:limit]


def fake_embeddings(texts):
    return [[1.0, 0.0] if "入门" in text or "初学" in text else [0.0, 1.0] for text in texts]


def ready(app):
    store = FakeStore()
    app.config.update(
        EMBEDDING_PROVIDER=fake_embeddings,
        CHAT_PROVIDER=lambda question, contexts, history: "可以从讲义开始。[1]",
        VECTOR_STORE=store,
    )
    with app.app_context():
        index_material(1, 1)
        index_material(2, 2)
    return store


def test_chunk_offsets_and_strategies():
    text = "# 标题\n\n" + "课程学习。" * 100
    for strategy in (None, {"type": "markdown"}, {"type": "delimiter", "delimiter": "。"}):
        chunks = split_text(text, strategy)
        assert chunks
        assert all(text[chunk.start_offset : chunk.end_offset] == chunk.body for chunk in chunks)
        assert all(len(chunk.body) <= 800 for chunk in chunks)
    assert split_text(text, {"type": "markdown"})[0].heading == "标题"


def test_existing_database_migrates_without_changing_body(tmp_path):
    path = tmp_path / "old.sqlite3"
    initialize(path, ["teacher", "a", "b"])
    app = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE_PATH": str(path),
                      "UPLOAD_DIR": str(tmp_path / "uploads")})
    with app.app_context():
        original = get_db().execute("SELECT body FROM knowledge_entries WHERE material_id=1").fetchone()[0]
        assert get_db().execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0] == 2
        assert get_db().execute("SELECT index_status FROM materials WHERE id=1").fetchone()[0] == "pending"
    create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE_PATH": str(path),
                "UPLOAD_DIR": str(tmp_path / "uploads")})
    with app.app_context():
        assert get_db().execute("SELECT body FROM knowledge_entries WHERE material_id=1").fetchone()[0] == original
        assert get_db().execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0] == 2


def test_search_modes_and_sources(app, client):
    ready(app)
    login(client, "student_a1", "student-a-test-password")
    keyword = client.post("/api/search", json={"q": "入门", "mode": "keyword"})
    assert keyword.status_code == 200
    assert keyword.json["hits"][0]["title"] == "A 班入门讲义"
    assert keyword.json["hits"][0]["source_url"].startswith("/materials?id=1&chunk=")
    assert "B 班" not in str(keyword.json)
    vector = client.post("/api/search", json={"q": "初学", "mode": "vector"})
    assert vector.status_code == 200
    assert vector.json["hits"][0]["material_id"] == 1
    hybrid = client.post("/api/search", json={"q": "入门", "mode": "hybrid"})
    assert hybrid.status_code == 200
    assert hybrid.json["hits"][0]["material_id"] == 1
    assert hybrid.json["hits"][0]["start_offset"] == 0


def test_cross_class_payload_and_client_class_are_ignored(app, client):
    store = ready(app)
    other = next(point for point in store.points.values() if point["payload"]["class_id"] == 2)
    store.query = lambda vector, class_id, limit: [
        {"id": other["id"], "payload": other["payload"], "score": 0.99},
    ]
    login(client, "student_a1", "student-a-test-password")
    response = client.post("/api/search?class_id=2", headers={"X-Class-Id": "2"},
                           json={"q": "实验", "mode": "vector", "class_id": 2})
    assert response.status_code == 200
    assert response.json["hits"] == []
    assert "B 班" not in str(response.json)


def test_answer_citations_and_no_evidence(app, client):
    store = ready(app)
    login(client, "student_a1", "student-a-test-password")
    answer = client.post("/api/ask", json={"q": "入门"})
    assert answer.status_code == 200
    assert answer.json["answer"].endswith("[1]")
    assert len(answer.json["citations"]) == 1
    assert answer.json["citations"][0]["number"] == 1
    store.query = lambda vector, class_id, limit: []
    app.config["CHAT_PROVIDER"] = lambda *args: (_ for _ in ()).throw(AssertionError("chat called"))
    missing = client.post("/api/ask", json={"q": "xyzunmatched"})
    assert missing.status_code == 200
    assert missing.json == {"answer": "资料中未找到相关内容", "citations": []}


def test_vector_outage_keeps_keyword_mode(app, client):
    store = ready(app)
    store.unavailable = True
    login(client, "student_a1", "student-a-test-password")
    assert client.post("/api/search", json={"q": "入门", "mode": "keyword"}).status_code == 200
    assert client.post("/api/search", json={"q": "入门", "mode": "vector"}).status_code == 503
    assert client.post("/api/search", json={"q": "入门", "mode": "hybrid"}).status_code == 503


def test_upload_failure_and_teacher_reindex(app, client):
    store = FakeStore()
    app.config.update(VECTOR_STORE=store,
                      EMBEDDING_PROVIDER=lambda texts: (_ for _ in ()).throw(GatewayUnavailable("offline")))
    login(client)
    uploaded = client.post("/api/materials", data={"file": (io.BytesIO("测试资料。".encode()), "lesson.md")})
    assert uploaded.status_code == 201
    assert uploaded.json["index_status"] == "failed"
    material_id = uploaded.json["id"]
    with app.app_context():
        assert get_db().execute("SELECT body FROM knowledge_entries WHERE material_id=?", (material_id,)).fetchone()[0] == "测试资料。"
        assert get_db().execute("SELECT index_status FROM knowledge_chunks WHERE material_id=?", (material_id,)).fetchone()[0] == "failed"
    app.config["EMBEDDING_PROVIDER"] = fake_embeddings
    rebuilt = client.post(f"/api/materials/{material_id}/reindex", json={"strategy": {"type": "auto"}})
    assert rebuilt.status_code == 200
    assert rebuilt.json["status"] == "ready"
    assert len(store.points) == 1
    point = next(iter(store.points.values()))
    assert "body" not in point["payload"]
    assert point["id"] == point["payload"]["chunk_id"]
    assert point["payload"]["chunk_index"] == 0
    assert "knowledge_entry_id" in point["payload"]
    second = client.post(f"/api/materials/{material_id}/reindex", json={
        "strategy": {"type": "delimiter", "delimiter": "。", "max_chars": 100, "overlap": 0},
    })
    assert second.status_code == 200
    assert point["id"] not in store.points
    assert len(store.points) == 1
    point = next(iter(store.points.values()))
    source = client.get(f"/materials?id={material_id}&chunk={point['id']}")
    assert b'<mark id="source">' in source.data
    client.post("/api/logout")
    login(client, "student_a1", "student-a-test-password")
    assert client.post(f"/api/materials/{material_id}/reindex", json={}).status_code == 403
    client.post("/api/logout")
    login(client)
    assert client.post("/api/materials/2/reindex", json={}).status_code == 404
    assert client.post(f"/api/materials/{material_id}/reindex", json={
        "strategy": {"type": "auto", "max_chars": 99},
    }).status_code == 400


def test_anonymous_search_rejected(client):
    assert client.post("/api/search", json={"q": "入门"}).status_code == 401
    assert client.post("/api/ask", json={"q": "入门"}).status_code == 401
