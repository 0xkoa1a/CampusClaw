"""Run the Week 6 synthetic MCP integration check against a loopback CampusClaw."""

import argparse
import ipaddress
import json
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)


TEACHER = ("teacher_a", "teacher-test-password")
STUDENT_A = ("student_a1", "student-a-test-password")
STUDENT_B = ("student_b1", "student-b-test-password")
MCP_SERVER_NAME = "campus-tools"
MCP_SERVER_URL = "http://mcp-demo:8090"
MCP_TOKEN_ENV = "MCP_AUTH_TOKEN"

INITIAL_MATERIALS = {
    "teacher_a": ("A 班入门讲义", "# A 班入门讲义\n\n本班材料示例。"),
    "student_b1": ("B 班实验说明", "# B 班实验说明\n\n仅 B 班可见。"),
}

EQUATION_TITLE = "week06-equation.md"
EQUATION_BODY = (
    "# WEEK06_SYNTH_EQUATION\n\n"
    "WEEK06_EQUATION_CONTEXT：解方程时先观察等式两边，再对两边做相同运算；"
    "移动未知数项之前检查符号。所有内容均为第六课合成验收材料。"
)
LANGUAGE_TITLE = "week06-language.txt"
LANGUAGE_BODY = (
    "# WEEK06_SYNTH_LANGUAGE\n\n"
    "WEEK06_LANGUAGE_CONTEXT：古诗中的比喻通过具体形象表达感受。"
    "本段是与方程问题无关的合成语文内容。"
)
UNBOUND_TITLE = "week06-unbound-secret.md"
UNBOUND_BODY = (
    "# WEEK06_UNBOUND_SECRET_MARKER\n\n"
    "WEEK06_UNBOUND_SECRET_MARKER：这段内容不绑定到任何智能体，"
    "不得进入模型请求或调用记录。"
)

MATH_SKILL_BODY = (
    "W6_MATH_SKILL_BODY_SENTINEL：使用已绑定资料引导学生检查方程下一步，"
    "不直接给出最终答案。"
)
UNHIT_SKILL_BODY = (
    "W6_UNHIT_SKILL_BODY_SENTINEL：仅在讨论古诗、文言文或修辞时使用本技能。"
)
CALCULATE_SKILL_BODY = (
    "W6_CALCULATE_SKILL_BODY_SENTINEL：学生要求四则运算时调用 calculate@campus-tools，"
    "依据工具返回解释结果。"
)
CONVERT_SKILL_BODY = (
    "W6_CONVERT_SKILL_BODY_SENTINEL：学生要求单位换算时调用 unit_convert@campus-tools，"
    "依据工具返回解释结果。"
)


class VerificationError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_loopback_base(base_url):
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise VerificationError("--base-url 必须是无凭据、无路径的 loopback HTTP(S) 地址")
    hostname = parsed.hostname.lower()
    if hostname != "localhost":
        try:
            if not ipaddress.ip_address(hostname).is_loopback:
                raise VerificationError("--base-url 只能指向 loopback")
        except ValueError as exc:
            raise VerificationError("--base-url 只能指向 loopback") from exc
    return base_url.rstrip("/")


class Api:
    def __init__(self, base_url):
        self.base_url = validate_loopback_base(base_url)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def _open(self, method, path, *, data=None, headers=None, timeout=45):
        request = Request(
            self.base_url + path,
            method=method,
            data=data,
            headers=headers or {},
        )
        try:
            return self.opener.open(request, timeout=timeout)
        except HTTPError as exc:
            raise VerificationError(f"{method} {path} 返回 HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise VerificationError(f"{method} {path} 连接失败（{type(exc).__name__}）") from None

    def json(self, method, path, *, payload=None, token=None, expected=200):
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if token:
            headers["Authorization"] = "Bearer " + token
        with self._open(method, path, data=body, headers=headers) as response:
            if response.status != expected:
                raise VerificationError(f"{method} {path} 返回 HTTP {response.status}")
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise VerificationError(f"{method} {path} 响应超过大小限制")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise VerificationError(f"{method} {path} 未返回有效 JSON") from None
        if not isinstance(value, dict):
            raise VerificationError(f"{method} {path} JSON 响应结构不正确")
        return value

    def upload(self, token, filename, text):
        boundary = "----week06-" + uuid.uuid4().hex
        content = text.encode("utf-8")
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: text/plain; charset=utf-8\r\n\r\n"
        ).encode("ascii") + content + f"\r\n--{boundary}--\r\n".encode("ascii")
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        with self._open("POST", "/api/materials", data=body, headers=headers) as response:
            if response.status != 201:
                raise VerificationError(f"POST /api/materials 返回 HTTP {response.status}")
            raw = response.read(64 * 1024)
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise VerificationError("材料上传未返回有效 JSON") from None
        if not isinstance(result, dict) or type(result.get("id")) is not int:
            raise VerificationError("材料上传响应缺少材料编号")
        return result

    def stream(self, token, conversation_id, question):
        data = json.dumps({"content": question}, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
        }
        path = f"/api/conversations/{conversation_id}/messages"
        with self._open("POST", path, data=data, headers=headers, timeout=180) as response:
            if response.status != 200 or "text/event-stream" not in response.headers.get("Content-Type", ""):
                raise VerificationError(f"POST {path} 未返回 SSE")
            events = []
            event_name = "message"
            data_lines = []
            byte_count = 0
            deadline = time.monotonic() + 180

            def append_event():
                nonlocal event_name, data_lines
                if not data_lines:
                    event_name = "message"
                    return
                try:
                    payload = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    raise VerificationError("SSE data 不是有效 JSON") from None
                events.append({"event": event_name, "data": payload})
                event_name = "message"
                data_lines = []

            for raw_line in response:
                byte_count += len(raw_line)
                if byte_count > 4 * 1024 * 1024:
                    raise VerificationError("SSE 输出超过大小限制")
                if time.monotonic() > deadline:
                    raise VerificationError("SSE 流超过 180 秒")
                try:
                    line = raw_line.decode("utf-8").rstrip("\r\n")
                except UnicodeDecodeError:
                    raise VerificationError("SSE 包含非法 UTF-8") from None
                if not line:
                    append_event()
                elif line.startswith("event:"):
                    event_name = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            append_event()

        meta = next((item["data"] for item in events if item["event"] == "meta"), None)
        done = next((item["data"] for item in events if item["event"] == "done"), None)
        stream_error = next((item["data"] for item in events if item["event"] == "error"), None)
        if stream_error is not None:
            raise VerificationError("真实模型 SSE 返回 error 事件")
        if not isinstance(meta, dict) or not isinstance(done, dict) or type(done.get("message_id")) is not int:
            raise VerificationError("SSE 未完整产生 meta 和 done")
        if not any(item["event"] == "delta" for item in events):
            raise VerificationError("SSE 没有真实回答增量")
        return {
            "events": events,
            "meta": meta,
            "done": done,
            "answer": "".join(
                item["data"]["text"]
                for item in events
                if item["event"] == "delta" and isinstance(item["data"], dict)
                and isinstance(item["data"].get("text"), str)
            ),
        }


def expect(condition, message):
    if not condition:
        raise VerificationError(message)


def skill_source(name, triggers, tools, body):
    return (
        f"名称：{name}\n"
        f"适用条件：{triggers}\n"
        f"工具：{tools}\n"
        "启用：是\n\n"
        f"{body}"
    )


def assert_initial_materials(api, username, token):
    expected_title, expected_body = INITIAL_MATERIALS[username]
    listing = api.json("GET", "/api/materials", token=token)
    materials = listing.get("materials")
    expect(isinstance(materials, list) and len(materials) == 1,
           f"{username} 的材料前置条件不符：需要恰好一篇初始化示例")
    item = materials[0]
    expect(item.get("title") == expected_title, f"{username} 已有材料不是初始化示例")
    detail = api.json("GET", f"/api/materials/{item['id']}", token=token)
    expect(detail.get("title") == expected_title and detail.get("body") == expected_body,
           f"{username} 初始化材料正文不匹配")
    return detail


def login(api, username, password):
    result = api.json(
        "POST",
        "/api/login",
        payload={"username": username, "password": password, "auth_mode": "bearer"},
    )
    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise VerificationError("测试账号未返回 Bearer 会话")
    return token


def safe_trace(api, token, conversation_id, question, login_secrets):
    traces = []
    for attempt in range(10):
        response = api.json(
            "GET",
            f"/api/conversations/{conversation_id}/traces",
            token=token,
        )
        traces = response.get("traces", [])
        complete = [item for item in traces if item.get("status") in {"complete", "error"}]
        if complete:
            break
        if attempt < 9:
            time.sleep(0.25)
    expect(bool(traces), "trace API 在有限重试后仍未保存本轮记录")
    item = traces[-1]
    expect(item.get("status") == "complete", "trace 记录状态不是 complete")
    events = item.get("events")
    expect(isinstance(events, list) and events, "trace 缺少调用事件")
    serialized = json.dumps(item, ensure_ascii=False)
    expect(question in serialized, "trace 未保存本轮合成问题")
    forbidden_values = [
        *login_secrets,
        TEACHER[1], STUDENT_A[1], STUDENT_B[1],
        INITIAL_MATERIALS["teacher_a"][1], INITIAL_MATERIALS["student_b1"][1],
        "UNBOUND_SECRET_MARKER",
    ]
    for secret in forbidden_values:
        expect(secret not in serialized, "trace 含有认证信息或非本次合成资料")
    expect("Authorization" not in serialized and "Bearer " not in serialized,
           "trace 含有传输凭据")
    forbidden_keys = {"authorization", "cookie", "password", "api_key", "access_token", "mcp_auth_token"}

    def has_forbidden_key(value):
        if isinstance(value, dict):
            return any(
                str(key).lower() in forbidden_keys or has_forbidden_key(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(has_forbidden_key(child) for child in value)
        return False

    for event in events:
        expect(not has_forbidden_key(event), "trace event 含凭据字段")
    return item


def request_bodies(trace):
    result = []
    for event in trace["events"]:
        if event.get("kind") != "llm_request":
            continue
        payload = event.get("payload", {})
        body = payload.get("body") if isinstance(payload, dict) else None
        if isinstance(body, dict):
            result.append((payload, body))
    return result


def messages_text(body):
    return "\n".join(
        str(item.get("content", ""))
        for item in body.get("messages", [])
        if isinstance(item, dict)
    )


def assert_real_stream_trace(trace):
    expect(
        any(
            payload.get("mode") != "test-provider"
            and body.get("stream") is True
            for payload, body in request_bodies(trace)
        ),
        "trace 未证明使用真实流式模型请求",
    )
    expect(
        any(event.get("kind") == "llm_sse_data" for event in trace["events"]),
        "trace 未保存真实模型 SSE 数据帧",
    )


def assert_mcp_tool_evidence(trace, discovered_tool, expected_result):
    bodies = request_bodies(trace)
    planning = [
        body for payload, body in bodies
        if payload.get("mode") != "test-provider" and isinstance(body.get("tools"), list)
    ]
    expect(bool(planning), f"{discovered_tool['name']} 没有真实工具规划请求")
    matched = []
    for body in planning:
        for item in body["tools"]:
            function = item.get("function", {}) if isinstance(item, dict) else {}
            if function.get("name") == discovered_tool["name"]:
                matched.append(function)
    expect(bool(matched), f"工具 schema 映射没有保留名称 {discovered_tool['name']}")
    expect(
        all(function.get("parameters") == discovered_tool["inputSchema"] for function in matched),
        f"{discovered_tool['name']} 的发现 schema 未原样进入模型请求",
    )
    tool_results = [
        event.get("payload", {})
        for event in trace["events"]
        if event.get("kind") == "tool_result"
    ]
    serialized_results = json.dumps(tool_results, ensure_ascii=False)
    expect(expected_result in serialized_results, f"trace 未保存 {discovered_tool['name']} 的 MCP 结果")
    expect(
        any(
            event.get("kind") == "mcp_request"
            and event.get("payload", {}).get("method") == "tools/call"
            for event in trace["events"]
        ),
        "trace 未保存 MCP tools/call 请求",
    )
    expect(
        any(event.get("kind") == "mcp_response" for event in trace["events"]),
        "trace 未保存 MCP 响应",
    )


def create_conversation(api, token, agent_id):
    result = api.json(
        "POST",
        "/api/conversations",
        payload={"agent_id": agent_id},
        token=token,
        expected=201,
    )
    conversation_id = result.get("conversation", {}).get("id")
    expect(type(conversation_id) is int, "会话创建响应缺少编号")
    return conversation_id


def run_turn(api, student_token, agent_id, question, result_key, report, login_secrets):
    conversation_id = create_conversation(api, student_token, agent_id)
    streamed = api.stream(student_token, conversation_id, question)
    trace = safe_trace(api, student_token, conversation_id, question, login_secrets)
    assert_real_stream_trace(trace)
    if streamed["done"]["message_id"] <= 0 or not streamed["answer"].strip():
        raise VerificationError(f"{result_key} 未保存非空真实回答")
    record = {
        "conversation_id": conversation_id,
        "message_id": streamed["done"]["message_id"],
        "delta_events": sum(event["event"] == "delta" for event in streamed["events"]),
        "skill_name": streamed["meta"].get("skill_name"),
        "citations": streamed["meta"].get("citations", []),
        "tool_calls": streamed["meta"].get("tool_calls", []),
        "trace_id": trace.get("id"),
        "trace_status": trace.get("status"),
        "trace": trace,
        "answer": streamed["answer"],
    }
    report["turns"][result_key] = record
    return conversation_id, streamed, trace


def verify(base_url, report):
    api = Api(base_url)
    tokens = {}
    try:
        tokens["teacher"] = login(api, *TEACHER)
        tokens["student_a"] = login(api, *STUDENT_A)
        tokens["student_b"] = login(api, *STUDENT_B)
        # Read-only safeguards all run before any material, skill, agent or server is created.
        assert_initial_materials(api, "teacher_a", tokens["teacher"])
        assert_initial_materials(api, "student_b1", tokens["student_b"])
        agents = api.json("GET", "/api/agents", token=tokens["teacher"]).get("agents")
        expect(agents == [], "教师账号已有 agent；为避免误测，本次没有写入验收数据")
        servers = api.json("GET", "/api/mcp/servers", token=tokens["teacher"]).get("servers")
        expect(isinstance(servers, list), "MCP server 清单结构不正确")
        expect(
            not any(item.get("name") == MCP_SERVER_NAME for item in servers),
            "campus-tools 已存在；为避免覆盖或重复写入，本次停止",
        )
        report["checks"].append("初始化材料、空 agent 清单和 server 名称前置条件通过")

        registered = api.json(
            "POST",
            "/api/mcp/servers",
            payload={
                "name": MCP_SERVER_NAME,
                "base_url": MCP_SERVER_URL,
                "token_env": MCP_TOKEN_ENV,
            },
            token=tokens["teacher"],
            expected=201,
        )
        server = registered.get("server", {})
        server_id = server.get("id")
        expect(type(server_id) is int and server.get("connected") is False, "MCP server 登记失败")
        expect("token" not in server, "MCP server API 回显了令牌")
        connected = api.json(
            "POST",
            f"/api/mcp/servers/{server_id}/connect",
            token=tokens["teacher"],
        ).get("server", {})
        discovered = connected.get("tools")
        expect(connected.get("connected") is True and isinstance(discovered, list),
               "MCP server 未成功连接和发现工具")
        tool_map = {tool.get("name"): tool for tool in discovered if isinstance(tool, dict)}
        expect({"calculate", "unit_convert"} <= set(tool_map),
               "MCP 发现清单缺少 calculate 或 unit_convert")
        for name, required in {
            "calculate": {"operation", "a", "b"},
            "unit_convert": {"value", "from_unit", "to_unit"},
        }.items():
            schema = tool_map[name].get("inputSchema", {})
            expect(
                schema.get("type") == "object"
                and set(schema.get("required", [])) == required
                and schema.get("additionalProperties") is False,
                f"{name} 的发现 schema 不符合约定",
            )
        report["checks"].append("campus-tools 已连接，calculate 与 unit_convert schema 已发现")

        materials = {}
        for key, filename, title, body in (
            ("equation", "week06-equation.md", EQUATION_TITLE, EQUATION_BODY),
            ("language", "week06-language.txt", LANGUAGE_TITLE, LANGUAGE_BODY),
            ("unbound", "week06-unbound-secret.md", UNBOUND_TITLE, UNBOUND_BODY),
        ):
            uploaded = api.upload(tokens["teacher"], filename, body)
            expect(uploaded.get("index_status") == "ready",
                   f"{filename} 未完成索引；真实 RAG 验收不能继续")
            detail = api.json("GET", f"/api/materials/{uploaded['id']}", token=tokens["teacher"])
            expect(detail.get("title") == title and detail.get("body") == body,
                   f"{filename} 上传后正文不匹配")
            materials[key] = uploaded["id"]
        report["checks"].append("三篇合成资料已上传并完成索引")

        skill_specs = (
            ("math", "数学解题引导", "方程,解方程,等式", "", MATH_SKILL_BODY),
            ("unhit", "未命中语文技能", "古诗,文言文,修辞", "", UNHIT_SKILL_BODY),
            ("calculate", "MCP四则计算", "计算,相加,加法", "calculate@campus-tools", CALCULATE_SKILL_BODY),
            ("convert", "MCP单位换算", "换算,单位换算,厘米", "unit_convert@campus-tools", CONVERT_SKILL_BODY),
        )
        skill_ids = {}
        for key, name, triggers, tools, body in skill_specs:
            response = api.json(
                "POST",
                "/api/skills",
                payload={"source": skill_source(name, triggers, tools, body)},
                token=tokens["teacher"],
                expected=201,
            )
            skill = response.get("skill", {})
            expect(type(skill.get("id")) is int, f"技能 {name} 创建失败")
            skill_ids[key] = skill["id"]

        agent_specs = (
            (
                "no-tool-and-knowledge",
                "W6无工具与知识",
                [skill_ids["math"], skill_ids["unhit"]],
                [materials["equation"], materials["language"]],
            ),
            ("calculate", "W6四则计算", [skill_ids["calculate"]], [materials["equation"]]),
            ("convert", "W6单位换算", [skill_ids["convert"]], []),
        )
        agent_ids = {}
        for key, name, bound_skills, bound_materials in agent_specs:
            response = api.json(
                "POST",
                "/api/agents",
                payload={
                    "name": name,
                    "role_prompt": "你是课程学习助手，只依据当前问题、绑定资料和可用工具作答。",
                    "skill_ids": bound_skills,
                    "material_ids": bound_materials,
                    "tool_names": [],
                },
                token=tokens["teacher"],
                expected=201,
            )
            agent = response.get("agent", {})
            expect(type(agent.get("id")) is int, f"智能体 {name} 创建失败")
            agent_ids[key] = agent["id"]
        report["checks"].append("四项技能和三个验收 agent 已创建")

        question_no_tool = "请用一句话说说你能怎样帮助我安排一次普通的学习计划。"
        no_tool_id, no_tool, no_tool_trace = run_turn(
            api, tokens["student_a"], agent_ids["no-tool-and-knowledge"],
            question_no_tool, "no_tool", report, list(tokens.values()),
        )
        no_tool_bodies = request_bodies(no_tool_trace)
        expect(not no_tool["meta"].get("tool_calls"), "无工具问题意外产生工具调用")
        expect(
            all("tools" not in body for _, body in no_tool_bodies),
            "无工具 agent 的模型请求包含工具 schema",
        )
        report["checks"].append("无工具问题完成真实流式回答，未发送工具 schema")

        question_knowledge = "方程 x + 2 = 5，按照资料提示我第一步应该检查什么？"
        knowledge_id, knowledge, knowledge_trace = run_turn(
            api, tokens["student_a"], agent_ids["no-tool-and-knowledge"],
            question_knowledge, "knowledge", report, list(tokens.values()),
        )
        knowledge_serialized = json.dumps(knowledge_trace, ensure_ascii=False)
        expect(EQUATION_BODY.split("：")[1][:24] in knowledge_serialized,
               "知识请求 trace 未包含方程资料")
        expect(MATH_SKILL_BODY in knowledge_serialized, "知识请求 trace 未包含命中的数学技能正文")
        expect(UNHIT_SKILL_BODY not in knowledge_serialized, "未命中的语文技能正文进入了 trace")
        expect(UNBOUND_BODY not in knowledge_serialized and "WEEK06_UNBOUND_SECRET_MARKER" not in knowledge_serialized,
               "未绑定资料进入了知识请求 trace")
        expect(bool(knowledge["meta"].get("citations")), "知识问题没有真实检索引用")
        expect(knowledge["meta"].get("skill_name") == "数学解题引导",
               "知识问题没有命中数学解题引导技能")
        report["checks"].append("知识问题含命中资料和技能，未命中技能及未绑定资料均未进入 trace")

        question_calculate = "请计算 23 + 19（加法），调用 calculate 工具并告诉我结果。"
        calculate_id, calculate_turn, calculate_trace = run_turn(
            api, tokens["student_a"], agent_ids["calculate"],
            question_calculate, "calculate", report, list(tokens.values()),
        )
        calc_calls = calculate_turn["meta"].get("tool_calls", [])
        expect(any(item.get("tool") == "calculate@campus-tools" and item.get("status") == "ok"
                   for item in calc_calls), "真实模型没有成功调用 calculate")
        calculate_trace_text = json.dumps(calculate_trace, ensure_ascii=False)
        expect(CALCULATE_SKILL_BODY in calculate_trace_text, "calculate 技能正文未进入 trace")
        assert_mcp_tool_evidence(calculate_trace, tool_map["calculate"], "42")
        report["checks"].append("真实模型调用 calculate，schema、工具结果和 MCP 请求响应均已留痕")

        question_convert = (
            "请调用 unit_convert 工具，value=150、from_unit=cm、to_unit=m，"
            "告诉我换算后的数值。"
        )
        convert_id, convert_turn, convert_trace = run_turn(
            api, tokens["student_a"], agent_ids["convert"],
            question_convert, "unit_convert", report, list(tokens.values()),
        )
        convert_calls = convert_turn["meta"].get("tool_calls", [])
        expect(any(item.get("tool") == "unit_convert@campus-tools" and item.get("status") == "ok"
                   for item in convert_calls), "真实模型没有成功调用 unit_convert")
        convert_trace_text = json.dumps(convert_trace, ensure_ascii=False)
        expect(CONVERT_SKILL_BODY in convert_trace_text, "unit_convert 技能正文未进入 trace")
        assert_mcp_tool_evidence(convert_trace, tool_map["unit_convert"], "1.5")
        report["checks"].append("真实模型调用 unit_convert，schema、工具结果和 MCP 请求响应均已留痕")

        audit = api.json("GET", "/api/mcp/tool-calls", token=tokens["teacher"]).get("tool_calls", [])
        for conversation_id, ref in (
            (calculate_id, "calculate@campus-tools"),
            (convert_id, "unit_convert@campus-tools"),
        ):
            expect(
                any(item.get("conversation_id") == conversation_id
                    and item.get("tool_ref") == ref and item.get("status") == "ok"
                    for item in audit),
                f"{ref} 缺少成功审计",
            )
        report["checks"].append("教师审计 API 中存在两条对应的 ok 调用")

        disconnected = api.json(
            "POST",
            f"/api/mcp/servers/{server_id}/disconnect",
            token=tokens["teacher"],
        ).get("server", {})
        expect(disconnected.get("connected") is False and disconnected.get("tools") == [],
               "断开 MCP 后连接状态或发现缓存未清空")
        question_denied = "请调用 calculate 工具计算 23 + 19。"
        denied_id, denied_turn, denied_trace = run_turn(
            api, tokens["student_a"], agent_ids["calculate"],
            question_denied, "disconnected", report, list(tokens.values()),
        )
        denied_calls = denied_turn["meta"].get("tool_calls", [])
        expect(any(item.get("tool") == "calculate@campus-tools" and item.get("status") == "denied"
                   for item in denied_calls), "断开后 MCP 技能没有标记为 denied")
        expect(
            not any(
                event.get("kind") == "mcp_request"
                and event.get("payload", {}).get("method") == "tools/call"
                for event in denied_trace["events"]
            ),
            "MCP 断开后仍发送了 tools/call",
        )
        denied_audit = api.json(
            "GET", "/api/mcp/tool-calls", token=tokens["teacher"]
        ).get("tool_calls", [])
        expect(
            any(item.get("conversation_id") == denied_id
                and item.get("tool_ref") == "calculate@campus-tools"
                and item.get("status") == "denied" for item in denied_audit),
            "断开后的 denied 状态未写入审计",
        )
        report["checks"].append("断开后已有 MCP 技能的新问题 denied、无远端调用、仍完成真实流回答")
        report["status"] = "passed"
    finally:
        for token in tokens.values():
            try:
                api.json("POST", "/api/logout", token=token, expected=200)
            except VerificationError:
                pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18082")
    parser.add_argument("--output", type=Path, help="保存合成验收结果 JSON")
    args = parser.parse_args()

    report = {
        "status": "running",
        "base_url": None,
        "checks": [],
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
        # Avoid dumping exception reprs that could carry request details.
        report["status"] = "failed"
        report["error"] = f"验收中断（{type(exc).__name__}）"

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
