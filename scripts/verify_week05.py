"""Real HTTP stream timing and synthetic evidence verification. No credentials printed."""

import argparse
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

from app.streaming import sse_data


def verify(base):
    # This verifier is deliberately confined to the isolated public-test-account service.
    from urllib.parse import urlsplit
    if urlsplit(base).hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("verification requires a loopback SSH tunnel or local test service")

    def call(method, path, data=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = Request(base + path, method=method, headers=headers,
                          data=json.dumps(data, ensure_ascii=False).encode() if data is not None else None)
        with urlopen(request, timeout=90) as response:
            return json.load(response)

    credentials = {"teacher_a": "teacher-test-password", "student_a1": "student-a-test-password"}
    tokens = {name: call("POST", "/api/login", {"username": name, "password": password, "auth_mode": "bearer"})["access_token"] for name, password in credentials.items()}
    teacher, student = tokens["teacher_a"], tokens["student_a1"]
    try:
        agents = call("GET", "/api/agents", token=teacher)["agents"]
        agent = next(item for item in agents if item["name"] == "数学解题助手")
        skills = call("GET", "/api/skills", token=teacher)["skills"]
        skill = next(item for item in skills if item["id"] in agent["skill_ids"])
        materials = [call("GET", f"/api/materials/{mid}", token=teacher) for mid in agent["material_ids"]]
        expected = "# 方程学习笔记\n\n方程两边做相同运算保持相等。去括号时要乘到每一项。整理未知数项之前先检查符号。只描述下一步，不列出题目的最终得数。\n\n合成验收资料，无真实学生信息。"
        if len(materials) != 1 or materials[0]["body"] != expected:
            raise ValueError("Verifier refuses non-fixture teaching material")
        cid = call("POST", "/api/conversations", {"agent_id": agent["id"]}, student)["conversation"]["id"]

        def turn(question):
            request = Request(base + f"/api/conversations/{cid}/messages", method="POST",
                              headers={"Authorization": "Bearer " + student, "Content-Type": "application/json"},
                              data=json.dumps({"content": question}, ensure_ascii=False).encode())
            begin = time.monotonic()
            records, fragments, meta, done = [], [], None, None
            with urlopen(request, timeout=90) as response:
                for raw in sse_data(response):
                    event = json.loads(raw)
                    records.append(round(time.monotonic() - begin, 4))
                    if "citations" in event:
                        meta = event
                    elif "text" in event:
                        fragments.append(event["text"])
                    elif "message_id" in event and "error" not in event:
                        done = event
                    elif "error" in event:
                        raise RuntimeError("real gateway stream emitted an error")
            if meta is None or done is None or len(fragments) < 2:
                raise RuntimeError("Expected multiple real incremental frames and a saved message")
            history = call("GET", f"/api/conversations/{cid}", token=student)["messages"]
            stored = next(item for item in history if item["id"] == done["message_id"])
            answer = "".join(fragments)
            if stored["content"] != answer or stored["status"] != "complete":
                raise RuntimeError("stream and persisted content disagree")
            return {"delta_frames": len(fragments), "elapsed_seconds": records[-1], "frame_times_seconds": records,
                    "skill_name": meta["skill_name"], "citations": meta["citations"], "answer": answer}

        grounded = turn("方程 x+2=5，我应该先检查哪一步？请只提示下一步。")
        if not grounded["citations"] or grounded["skill_name"] != skill["name"]:
            raise RuntimeError("Expected bound material and guidance skill")
        if not re.search(r"\[\d+\]", grounded["answer"]):
            raise RuntimeError("Grounded answer lacks an explicit source number")
        empty_agent = call("POST", "/api/agents", {"name": "无资料验收-" + str(time.time_ns()), "role_prompt": "简短给出学习建议，不声称来源于材料。", "material_ids": []}, teacher)["agent"]
        cid = call("POST", "/api/conversations", {"agent_id": empty_agent["id"]}, student)["conversation"]["id"]
        ungrounded = turn("请给我一个检查方程运算是否正确的学习建议。")
        if ungrounded["citations"]:
            raise RuntimeError("Ungrounded answer must have no citations")
        if re.search(r"\[\d+\]", ungrounded["answer"]):
            raise RuntimeError("Ungrounded answer has a fabricated source number")
        call("PUT", f"/api/agents/{empty_agent['id']}", {"enabled": False}, teacher)
        return {"grounded": grounded, "ungrounded": ungrounded}
    finally:
        for token in tokens.values():
            call("POST", "/api/logout", token=token)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18082")
    parser.add_argument("--output", type=Path, help="save generated synthetic verification JSON")
    args = parser.parse_args()
    result = json.dumps(verify(args.base_url.rstrip("/")), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
