"""Run one selected MCP supplement case against the initialized Week 6 fixture."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_week06 import (  # noqa: E402
    MCP_SERVER_NAME,
    STUDENT_A,
    TEACHER,
    Api,
    VerificationError,
    assert_real_stream_trace,
    create_conversation,
    login,
    safe_trace,
    validate_loopback_base,
)


BASE_URL = "http://127.0.0.1:18088"
AGENT_NAME = "W6四则计算"
ERROR_QUESTION = "请实际调用calculate计算23+19，并根据工具执行结果解释"
QUOTA_QUESTION = "请计算：先调用calculate计算23+19，再根据上次工具结果调用calculate把结果乘2，分两次调用"


def verify(case):
    api = Api(BASE_URL)
    tokens = {}
    try:
        tokens["teacher"] = login(api, *TEACHER)
        tokens["student"] = login(api, *STUDENT_A)
        servers = api.json("GET", "/api/mcp/servers", token=tokens["teacher"]).get("servers", [])
        server = next((item for item in servers if item.get("name") == MCP_SERVER_NAME), None)
        if not isinstance(server, dict) or type(server.get("id")) is not int:
            raise VerificationError("未找到已初始化的 campus-tools MCP server")
        agents = api.json("GET", "/api/agents", token=tokens["teacher"]).get("agents", [])
        agent = next((item for item in agents if item.get("name") == AGENT_NAME), None)
        if not isinstance(agent, dict) or type(agent.get("id")) is not int:
            raise VerificationError("未找到已初始化的 W6 四则计算 agent")
        if case == "error":
            if server.get("connected") is not True:
                raise VerificationError("error case 要求先由主流程连接 campus-tools")
        else:
            connected = api.json("POST", f"/api/mcp/servers/{server['id']}/connect",
                                 token=tokens["teacher"]).get("server", {})
            if connected.get("connected") is not True:
                raise VerificationError("campus-tools 未能重新连接")

        question = ERROR_QUESTION if case == "error" else QUOTA_QUESTION
        conversation_id = create_conversation(api, tokens["student"], agent["id"])
        streamed = api.stream(tokens["student"], conversation_id, question)
        trace = safe_trace(api, tokens["student"], conversation_id, question, list(tokens.values()))
        assert_real_stream_trace(trace)
        answer = streamed.get("answer", "")
        done_id = streamed.get("done", {}).get("message_id")
        if trace.get("status") != "complete" or not answer.strip() or type(done_id) is not int:
            raise VerificationError("真实模型回答或 trace 未成功完成")
        tool_calls = streamed["meta"].get("tool_calls", [])
        events = trace.get("events", [])
        mcp_calls = sum(event.get("kind") == "mcp_request"
                        and isinstance(event.get("payload"), dict)
                        and event["payload"].get("method") == "tools/call" for event in events)
        common = {"status": "passed", "case": case, "base_url": validate_loopback_base(BASE_URL),
                  "server": MCP_SERVER_NAME, "agent": AGENT_NAME, "conversation_id": conversation_id,
                  "tool_calls": tool_calls, "answer": answer, "done_message_id": done_id,
                  "trace_status": trace["status"]}
        if case == "error":
            if not any(item.get("tool") == f"calculate@{MCP_SERVER_NAME}" and item.get("status") == "error"
                       for item in tool_calls if isinstance(item, dict)) or mcp_calls < 1:
                raise VerificationError("未观察到真实 tools/call 尝试及 calculate error tool_call")
            common["tool_unavailable"] = {"observed": True, "mcp_tools_call_requests": mcp_calls}
            return common

        planning = sum(event.get("kind") == "llm_request"
                       and isinstance(event.get("payload"), dict)
                       and isinstance(event["payload"].get("body"), dict)
                       and event["payload"]["body"].get("stream") is False for event in events)
        if planning != 1:
            raise VerificationError("quota case 要求 trace 中恰好一次 stream=false 规划请求")
        if mcp_calls != 1:
            raise VerificationError("quota case 要求 trace 中恰好一次 tools/call 请求")
        common.update(planning_requests_stream_false=planning, mcp_tools_call_requests=mcp_calls)
        return common
    finally:
        for token in tokens.values():
            try:
                api.json("POST", "/api/logout", token=token, expected=200)
            except VerificationError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="保存摘要 JSON，不包含原始 trace")
    parser.add_argument("--case", choices=("error", "quota"), default="quota")
    args = parser.parse_args()
    try:
        result = verify(args.case)
    except VerificationError as exc:
        result = {"status": "failed", "error": str(exc)}
    except Exception as exc:
        result = {"status": "failed", "error": f"验收中断（{type(exc).__name__}）"}
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
