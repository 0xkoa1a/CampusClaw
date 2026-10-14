"""Fresh, synthetic fifth-lesson environment; real gateway by default."""

import argparse
import io
import secrets
import time
from pathlib import Path

from app import create_app
from app.db import get_db


def make_app(directory, stub=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "evidence.sqlite3").exists():
        raise RuntimeError("Use a fresh directory; an existing evidence database is never overwritten")
    app = create_app({
        "SECRET_KEY": secrets.token_hex(32), "DATABASE_PATH": str(directory / "evidence.sqlite3"),
        "UPLOAD_DIR": str(directory / "uploads"), "QDRANT_COLLECTION": "campusclaw_week05_" + secrets.token_hex(8),
        "SESSION_COOKIE_SECURE": False,
        "SEED_TEACHER_PASSWORD": "teacher-test-password", "SEED_STUDENT_A_PASSWORD": "student-a-test-password",
        "SEED_STUDENT_B_PASSWORD": "student-b-test-password", "AI_TIMEOUT_SECONDS": 45,
    })
    if stub:
        class Store:
            def __init__(self): self.points = {}
            def upsert(self, points): self.points.update({point["id"]: point for point in points})
            def delete(self, identifiers):
                for identifier in identifiers: self.points.pop(identifier, None)
            def query(self, vector, class_id, limit, material_ids=None):
                return [{"id": point["id"], "payload": point["payload"], "score": .9} for point in self.points.values()
                        if point["payload"]["class_id"] == class_id and (material_ids is None or point["payload"]["material_id"] in material_ids)][:limit]
        def provider(messages):
            text = "请先检查方程两边是否做了相同的运算，再尝试整理未知数项。[1]"
            for i in range(0, len(text), 3):
                time.sleep(.04)
                yield text[i:i + 3]
        app.config.update(VECTOR_STORE=Store(), EMBEDDING_PROVIDER=lambda texts: [[1., 0.] for _ in texts],
                          STREAM_PROVIDER=provider)
    client = app.test_client()
    client.post("/api/login", json={"username": "teacher_a", "password": "teacher-test-password"})
    ids = []
    for title, body in [
        ("A班-合成数学材料.md", "# 方程学习笔记\n\n方程两边做相同运算保持相等。去括号时要乘到每一项。整理未知数项之前先检查符号。只描述下一步，不列出题目的最终得数。\n\n合成验收资料，无真实学生信息。"),
        ("A班-合成语文材料.md", "# 阅读学习笔记\n\n找中心句时，先比较开头与结尾，再看反复出现的词语。先指出应检查的位置，不直接替学生写出答案。\n\n合成验收资料，无真实学生信息。"),
    ]:
        result = client.post("/api/materials", data={"file": (io.BytesIO(body.encode()), title)})
        if result.status_code != 201 or result.json["index_status"] != "ready":
            raise RuntimeError("Synthetic material indexing failed; verify the real gateway and vector service")
        ids.append(result.json["id"])
    source = "名称：数学解题引导\n适用条件：方程,去括号,数学\n资料：数学\n工具：knowledge_search\n启用：是\n\n学生卡在某一步时，只指出下一步该检查什么。不写最终答案、得数或完整过程。依据数学材料，标明出处。"
    skill = client.post("/api/skills", json={"source": source}).json["skill"]
    agent = client.post("/api/agents", json={"name": "数学解题助手", "role_prompt": "你是耐心的数学老师，帮助学生自己找到下一步。简短回答。", "skill_ids": [skill["id"]], "material_ids": [ids[0]]}).json["agent"]
    client.post("/api/agents", json={"name": "语文学习助手", "role_prompt": "帮助学生定位阅读线索，简短回答。", "material_ids": [ids[1]]})
    client.post("/api/logout")
    with app.app_context():
        app.extensions["week05_fixture"] = {"agent_id": agent["id"], "skill_id": skill["id"], "material_ids": ids,
                                            "mode": "stub" if stub else "real-gateway"}
        assert get_db().execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18082)
    parser.add_argument("--stub-model", action="store_true", help="explicit local deterministic UI test; not real AI evidence")
    args = parser.parse_args()
    if args.stub_model and args.host != "127.0.0.1":
        parser.error("stub mode is loopback only")
    app = make_app(args.data_dir, args.stub_model)
    print("Week05 evidence environment:", app.extensions["week05_fixture"], flush=True)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
