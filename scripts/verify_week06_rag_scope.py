"""Verify that a real Week 6 RAG request receives only part of a bound document."""

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_week06 import (  # noqa: E402
    Api,
    STUDENT_A,
    TEACHER,
    VerificationError,
    expect,
    login,
    request_bodies,
    run_turn,
    validate_loopback_base,
)


SYNTHETIC_PROJECT = "W6-RAG-SCOPE-SYNTHETIC"
DOCUMENT_FILENAME = "W6-RAG-SCOPE-SYNTHETIC-long-document.md"
AGENT_NAME = "W6-RAG-SCOPE-SYNTHETIC"
QUESTION = "等式应该怎样检查？"
SECTION_COUNT = 8
SECTION_MARKERS = [f"BOUND_SECTION_{index}" for index in range(1, SECTION_COUNT + 1)]
SECTION_SENTENCES = (
    "学习时先读清等式两边的表达，再确认等号表示两边数值相等，而不是提示只看左边。",
    "检查等式可以从已知条件开始，逐项核对数字、运算符和未知量的位置，避免遗漏条件。",
    "如果要对等式进行变形，应当说明两边执行了同一种运算，并检查变形前后的关系。",
    "完成计算后，把得到的数值代回原等式，分别计算左右两边，再比较结果是否相同。",
    "当等式中出现括号或分数时，先按规则整理表达式，并保留每一步可复查的中间结果。",
)


def build_document():
    sections = []
    for index, marker in enumerate(SECTION_MARKERS, start=1):
        paragraphs = [
            marker,
            f"本节主题：等式的检查方法。这里是 W6 合成范围验证的第 {index} 节。",
        ]
        sentence_index = 0
        while len("\n".join(paragraphs)) < 600:
            sentence = SECTION_SENTENCES[(index + sentence_index) % len(SECTION_SENTENCES)]
            paragraphs.append(f"第 {index} 节练习说明：{sentence}")
            sentence_index += 1
        sections.append(f"## 第 {index} 节：等式检查练习 {index}\n\n" + "\n\n".join(paragraphs))
    return "# W6 合成等式长文档范围验证\n\n" + "\n\n".join(sections)


def verify(base_url, report):
    api = Api(base_url)
    tokens = {}
    try:
        tokens["teacher"] = login(api, *TEACHER)
        tokens["student"] = login(api, *STUDENT_A)

        agents_response = api.json("GET", "/api/agents", token=tokens["teacher"])
        agents = agents_response.get("agents")
        expect(isinstance(agents, list), "agent 清单响应结构不正确")
        expect(
            all(isinstance(item, dict) and str(item.get("name", "")).startswith("W6")
                for item in agents),
            "存在名称不以 W6 开头的 agent；为避免误测，尚未写入验收数据",
        )
        expect(not any(item.get("name") == AGENT_NAME for item in agents),
               "合成验证 agent 已存在；为避免重名或覆盖，停止运行")

        materials_response = api.json("GET", "/api/materials", token=tokens["teacher"])
        materials = materials_response.get("materials")
        expect(isinstance(materials, list), "材料清单响应结构不正确")
        expect(not any(item.get("title") == DOCUMENT_FILENAME for item in materials),
               "合成长文档已存在；为避免重复写入，停止运行")
        report["preconditions"] = {
            "all_existing_agents_start_with_W6": True,
            "existing_agent_count": len(agents),
            "synthetic_agent_name_available": True,
            "synthetic_material_filename_available": True,
        }

        document = build_document()
        section_lengths = [
            len(section.split("\n\n", 1)[1])
            for section in document.split("\n\n## 第 ")[1:]
        ]
        expect(len(section_lengths) == SECTION_COUNT, "合成材料章节数不是 8")
        expect(all(580 <= length <= 720 for length in section_lengths),
               "合成材料每节长度不在约 600 字符范围内")
        for marker in SECTION_MARKERS:
            expect(document.count(marker) == 1, "合成材料章节标记不唯一")

        upload = api.upload(tokens["teacher"], DOCUMENT_FILENAME, document)
        expect(upload.get("index_status") == "ready", "长文档未完成索引，不能验证真实 RAG")
        material_id = upload["id"]
        material = api.json(
            "GET", f"/api/materials/{material_id}", token=tokens["teacher"]
        )
        expect(material.get("title") == DOCUMENT_FILENAME and material.get("body") == document,
               "服务端保存的合成材料标题或正文与上传内容不符")

        agent_response = api.json(
            "POST",
            "/api/agents",
            payload={
                "name": AGENT_NAME,
                "role_prompt": "你是 W6 合成范围验证助手，只依据唯一绑定的长文档回答等式检查问题。",
                "skill_ids": [],
                "material_ids": [material_id],
                "tool_names": [],
            },
            token=tokens["teacher"],
            expected=201,
        )
        agent = agent_response.get("agent", {})
        agent_id = agent.get("id")
        expect(type(agent_id) is int, "合成范围验证 agent 创建失败")
        expect(agent.get("skill_ids") == [] and agent.get("material_ids") == [material_id]
               and agent.get("tool_names") == [],
               "验证 agent 未做到仅绑定长文档且不绑定技能或工具")

        _, streamed, trace = run_turn(
            api,
            tokens["student"],
            agent_id,
            QUESTION,
            "rag_scope",
            report,
            list(tokens.values()),
        )
        citations = streamed["meta"].get("citations", [])
        expect(isinstance(citations, list) and len(citations) <= 4,
               "真实回答引用数超过 4 或引用结构不正确")
        request_messages = []
        for payload, body in request_bodies(trace):
            if payload.get("mode") == "test-provider":
                continue
            messages = body.get("messages")
            if isinstance(messages, list):
                request_messages.extend(
                    str(message.get("content", ""))
                    for message in messages
                    if isinstance(message, dict)
                )
        prompt_text = "\n".join(request_messages)
        expect(bool(prompt_text), "trace 中没有真实模型 messages")
        included_markers = [marker for marker in SECTION_MARKERS if marker in prompt_text]
        expect(bool(included_markers), "真实模型 messages 未包含任何绑定文档章节标记")
        expect(len(included_markers) < SECTION_COUNT,
               "真实模型 messages 包含了全部 8 节标记，不能证明只传入部分切片")
        expect(document not in prompt_text,
               "完整合成文档出现在真实模型 messages 中")
        expect(not streamed["meta"].get("tool_calls"),
               "无技能、无工具的 RAG 验证 agent 意外产生工具调用")

        report["status"] = "passed"
        report["summary"] = {
            "synthetic_project": SYNTHETIC_PROJECT,
            "material_title": material.get("title"),
            "material_id": material_id,
            "agent_name": AGENT_NAME,
            "agent_id": agent_id,
            "question": QUESTION,
            "section_count": SECTION_COUNT,
            "section_lengths_chars": section_lengths,
            "citation_count": len(citations),
            "prompt_section_markers": included_markers,
            "prompt_section_marker_count": len(included_markers),
            "complete_document_in_prompt": False,
            "real_streaming_answer_received": bool(streamed["answer"].strip()),
            "trace_id": trace.get("id"),
        }
    finally:
        for token in tokens.values():
            try:
                api.json("POST", "/api/logout", token=token, expected=200)
            except VerificationError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="CampusClaw loopback URL")
    parser.add_argument("--output", type=Path, required=True, help="完整 summary 与 trace JSON 输出路径")
    args = parser.parse_args()

    report = {
        "status": "running",
        "synthetic_project": SYNTHETIC_PROJECT,
        "base_url": None,
        "summary": None,
        "turns": {},
        "error": None,
    }
    try:
        report["base_url"] = validate_loopback_base(args.base_url)
        verify(args.base_url, report)
    except VerificationError as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"验收中断（{type(exc).__name__}）"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "synthetic_project": SYNTHETIC_PROJECT,
        "summary": report["summary"],
        "error": report["error"],
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
