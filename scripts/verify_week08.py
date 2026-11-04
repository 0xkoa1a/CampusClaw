"""Verify Week 8 asynchronous grading through a loopback CampusClaw HTTP API."""

import argparse
import ipaddress
import json
import math
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


# Public synthetic accounts shared with the other classroom acceptance scripts.
TEACHER = ("teacher_a", "teacher-test-password")
STUDENT_A = ("student_a1", "student-a-test-password")
STUDENT_B = ("student_b1", "student-b-test-password")
POLL_SECONDS = 600


class VerificationError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_base_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise VerificationError("--base-url 必须是无凭据、无路径的 loopback HTTP(S) 地址")
    host = parsed.hostname.lower()
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise VerificationError("--base-url 只能指向 loopback")
    return value.rstrip("/")


class Api:
    def __init__(self, base_url):
        self.base_url = validate_base_url(base_url)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def json(self, method, path, *, payload=None, token=None, expected=200, timeout=20, key=None):
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if token:
            headers["Authorization"] = "Bearer " + token
        if key:
            headers["Idempotency-Key"] = key
        request = Request(self.base_url + path, method=method, data=body, headers=headers)
        try:
            response = self.opener.open(request, timeout=timeout)
        except HTTPError as exc:
            if exc.code != expected:
                raise VerificationError(f"{method} {path} 返回 HTTP {exc.code}，预期 {expected}") from None
            raw = exc.read(1024 * 1024 + 1)
            status = exc.code
        except (URLError, TimeoutError, OSError) as exc:
            raise VerificationError(f"{method} {path} 连接失败（{type(exc).__name__}）") from None
        else:
            with response:
                status = response.status
                raw = response.read(1024 * 1024 + 1)
        if status != expected:
            raise VerificationError(f"{method} {path} 返回 HTTP {status}，预期 {expected}")
        if len(raw) > 1024 * 1024:
            raise VerificationError(f"{method} {path} 响应超过大小限制")
        if not raw:
            return {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise VerificationError(f"{method} {path} 未返回有效 JSON") from None
        if not isinstance(value, dict):
            raise VerificationError(f"{method} {path} JSON 响应结构不正确")
        return value


def login(api, account):
    username, password = account
    result = api.json("POST", "/api/login", payload={
        "username": username, "password": password, "auth_mode": "bearer",
    })
    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise VerificationError("合成账号未返回 Bearer 会话")
    return token


def with_login(api, account, action):
    token = login(api, account)
    try:
        return action(token)
    finally:
        try:
            api.json("POST", "/api/logout", token=token)
        except VerificationError:
            pass


def load_state(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise VerificationError("state 文件不可读或不是有效 JSON") from None
    if not isinstance(value, dict):
        raise VerificationError("state 文件结构无效")
    return value


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def emit(args, result):
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered, flush=True)


def prepare(api, args):
    if args.state.exists():
        raise VerificationError('prepare 需要新的 state 路径，避免覆盖已有验收记录')
    state = {"kind": "week08-synthetic", "assignment_id": None, "task_ids": [], "firstkey": None}
    assignment = with_login(api, TEACHER, lambda token: api.json(
        "POST", "/api/assignments", token=token, expected=201,
        payload={"title": "第八课合成数学验收", "question": "计算 2 + 2。",
                 "reference_answer": "4", "rubric": "答案为4得满分。", "max_score": 100},
    ).get("assignment"))
    if not isinstance(assignment, dict) or type(assignment.get("id")) is not int:
        raise VerificationError("创建合成作业未返回编号")
    assignment_id = assignment["id"]
    state["assignment_id"] = assignment_id
    route = f"/api/assignments/{assignment_id}/submissions"
    key_prefix = "w8_" + uuid.uuid4().hex
    timings, task_ids = [], []

    def submit_batch(token):
        for i in range(20):
            key = f"{key_prefix}_{i}"
            started = time.perf_counter()
            result = submit(api, route, token, "2 + 2 = 4。", key)
            timings.append(time.perf_counter() - started)
            if "result" in result or result.get("status") != 'pending':
                raise VerificationError("提交响应不符合立即接收契约")
            identifier = result.get("task_id")
            if not isinstance(identifier, str) or not identifier:
                raise VerificationError("提交响应缺少 task_id")
            task_ids.append(identifier)
            if i == 0:
                state["firstkey"] = key
        replay = submit(api, route, token, "2 + 2 = 4。", state["firstkey"])
        if replay.get("task_id") != task_ids[0] or replay.get("replayed") is not True:
            raise VerificationError("相同幂等键未返回原 task")
        expect_http(api, route, token, "different content", state["firstkey"], 409)
        return True

    with_login(api, STUDENT_A, submit_batch)
    if len(set(task_ids)) != 20:
        raise VerificationError('20 次独立提交未产生20个任务')
    with_login(api, STUDENT_A, lambda token: check_pending(api, task_ids, token))
    state["task_ids"] = task_ids

    def check_class(token):
        api.json("GET", f"/api/assignments/{assignment_id}", token=token, expected=404)
    with_login(api, STUDENT_B, check_class)
    p95 = sorted(timings)[math.ceil(0.95 * len(timings)) - 1]
    state["acceptance_p95_seconds"] = round(p95, 6)
    save_state(args.state, state)
    emit(args, {"status": "prepared", "assignment_id": assignment_id, "task_count": len(task_ids),
                "all_202_without_result": True, "same_key_same_task": True,
                "same_key_different_content_409": True, "class_b_assignment_404": True,
                "all_pending_while_worker_stopped": True, "response_seconds": timings,
                "acceptance_p95_seconds": state["acceptance_p95_seconds"]})


def check_pending(api, identifiers, token):
    if any(task_request(api, identifier, token).get('status') != 'pending' for identifier in identifiers):
        raise VerificationError('消费者暂停期间仍出现非 pending 任务')


def submit(api, route, token, content, key):
    return api.json("POST", route, token=token, expected=202,
                    payload={"content": content}, timeout=30, key=key)


def expect_http(api, route, token, content, key, expected):
    api.json("POST", route, token=token, payload={"content": content},
             key=key, expected=expected)


def task_request(api, task_id, token):
    response = api.json("GET", f"/api/tasks/{task_id}", token=token)
    task = response.get("task")
    if not isinstance(task, dict):
        raise VerificationError("任务详情响应结构无效")
    return task


def poll_tasks(api, args, ids, *, crash=False, wait_running=False):
    deadline = time.monotonic() + POLL_SECONDS
    last = None
    def poll(token):
        nonlocal last
        while time.monotonic() < deadline:
            last = [task_request(api, task_id, token) for task_id in ids]
            if wait_running:
                task = last[0]
                if task.get("status") == "running":
                    emit(args, {"status": "running", "crash_task_id": ids[0],
                                "attempts_observed": task.get("attempts")})
                    return
                if task.get("status") in {"succeeded", "failed", "dead"}:
                    raise VerificationError(f"crash-wait-running 观察到终态 {task.get('status')}，无法验收崩溃重试")
            elif all(task.get("status") == "succeeded" for task in last):
                return
            elif any(task.get("status") in {"failed", "dead"} for task in last):
                raise VerificationError("至少一个批改任务进入失败终态")
            time.sleep(0.05 if wait_running else 0.5)
        raise VerificationError("任务轮询超过 600 秒")

    with_login(api, STUDENT_A, poll)
    if wait_running:
        return

    for task in last:
        result = task.get("result")
        if not isinstance(result, dict) or result.get("source") != "real-gateway":
            raise VerificationError("成功任务结果未标记为 real-gateway")
        score = result.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
            raise VerificationError("任务分数不在 0–100 范围")
    if crash and last[0].get("attempts", 0) < 2:
        raise VerificationError("crash task attempts 小于 2")
    emit(args, {"status": "passed", "task_count": len(last), "succeeded": len(last),
                "all_results_real_gateway": True,
                "attempts": last[0].get("attempts") if crash else None,
                "tasks": [{"task_id": item["id"], "status": item["status"],
                           "attempts": item["attempts"], "score": item["result"]["score"],
                           "source": item["result"]["source"]} for item in last]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18088")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", choices=("prepare", "verify", "crash-prepare", "crash-wait-running", "verify-crash"))
    args = parser.parse_args()
    try:
        api = Api(args.base_url)
        if args.command == "prepare":
            prepare(api, args)
            return 0
        if args.command == "verify":
            state = load_state(args.state)
            ids = state.get("task_ids")
            if not isinstance(ids, list) or len(ids) != 20:
                raise VerificationError("state 缺少 20 个合成 task_id")
            poll_tasks(api, args, ids)
        elif args.command == "crash-prepare":
            state = load_state(args.state)
            assignment_id = state.get("assignment_id")
            if type(assignment_id) is not int:
                raise VerificationError("state 缺少 assignment_id")
            route = f"/api/assignments/{assignment_id}/submissions"
            key = "w8_crash_" + uuid.uuid4().hex
            result = with_login(api, STUDENT_A, lambda token: submit(api, route, token, "2 + 2 = 4。", key))
            task_id = result.get("task_id")
            if "result" in result or result.get("status") not in {"pending", "running"} or not isinstance(task_id, str):
                raise VerificationError("crash submission 未立即接收")
            state["crash_task_id"] = task_id
            save_state(args.state, state)
            emit(args, {"status": "prepared", "crash_task_id": task_id})
        else:
            state = load_state(args.state)
            task_id = state.get("crash_task_id")
            if not isinstance(task_id, str) or not task_id:
                raise VerificationError("state 缺少 crash_task_id")
            poll_tasks(api, args, [task_id], crash=args.command == "verify-crash",
                       wait_running=args.command == "crash-wait-running")
        return 0
    except VerificationError as exc:
        result = {"status": "failed", "error": str(exc)}
    except Exception as exc:
        result = {"status": "failed", "error": f"验收中断（{type(exc).__name__}）"}
    emit(args, result)
    return 1


if __name__ == "__main__":
    sys.exit(main())
