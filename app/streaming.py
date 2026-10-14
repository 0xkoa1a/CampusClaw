"""Incremental upstream SSE decoding and citation filtering."""

import codecs
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app

from .gateway import GatewayUnavailable


def sse_data(stream):
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer, data = "", []
    read = getattr(stream, "read1", stream.read)
    while True:
        block = read(4096)
        buffer += decoder.decode(block, final=not block)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if not line:
                if data:
                    yield "\n".join(data)
                    data = []
            elif line.startswith("data:"):
                data.append(line[5:].lstrip(" "))
        if not block:
            if buffer.startswith("data:"):
                data.append(buffer[5:].lstrip(" "))
            if data:
                yield "\n".join(data)
            return


def chat_stream(messages):
    provider = current_app.config.get("STREAM_PROVIDER")
    if provider is not None:
        upstream = iter(provider(messages))
        try:
            for text in upstream:
                if not isinstance(text, str):
                    raise GatewayUnavailable("网关增量格式不正确")
                if text:
                    yield text
        finally:
            if hasattr(upstream, "close"):
                upstream.close()
        return
    base = current_app.config["EMBEDDING_BASE_URL"].rstrip("/")
    key = current_app.config["EMBEDDING_API_KEY"]
    if not base or not key:
        raise GatewayUnavailable("课程网关尚未配置")
    request = Request(base + "/chat/completions", method="POST",
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "text/event-stream"},
                      data=json.dumps({"model": current_app.config["CHAT_MODEL"], "messages": messages,
                                       "stream": True, "temperature": 0.2, "max_tokens": 450}, ensure_ascii=False).encode())
    deadline = time.monotonic() + current_app.config.get("STREAM_TIMEOUT_SECONDS", 120)
    try:
        with urlopen(request, timeout=current_app.config["AI_TIMEOUT_SECONDS"]) as response:
            if "text/event-stream" not in response.headers.get("Content-Type", ""):
                raise GatewayUnavailable("课程网关未提供流式响应")
            finished = False
            for payload in sse_data(response):
                if time.monotonic() > deadline:
                    raise GatewayUnavailable("回答超时")
                if payload.strip() == "[DONE]":
                    finished = True
                    break
                data = json.loads(payload)
                if "error" in data:
                    raise GatewayUnavailable("课程网关生成失败")
                choices = data.get("choices", [])
                if not choices:
                    continue  # Some gateways emit a final usage-only frame.
                choice = choices[0]
                text = choice.get("delta", {}).get("content")
                if text is not None:
                    if not isinstance(text, str):
                        raise GatewayUnavailable("课程网关增量格式不正确")
                    if text:
                        yield text
                if choice.get("finish_reason") is not None:
                    finished = True
            if not finished:
                raise GatewayUnavailable("课程网关流提前结束")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise GatewayUnavailable("课程网关流暂时不可用") from exc


class CitationFilter:
    def __init__(self, count):
        self.count = count
        self.pending = ""

    def feed(self, text, final=False):
        self.pending += text
        output = []
        while self.pending:
            if self.pending[0] != "[":
                index = self.pending.find("[")
                if index < 0:
                    output.append(self.pending)
                    self.pending = ""
                    break
                output.append(self.pending[:index])
                self.pending = self.pending[index:]
            match = re.match(r"\[(\d+)\]", self.pending)
            if match:
                if 1 <= int(match[1]) <= self.count:
                    output.append(match[0])
                self.pending = self.pending[len(match[0]):]
            elif re.fullmatch(r"\[\d*", self.pending) and len(self.pending) < 32:
                if final:
                    self.pending = ""  # Do not leave an unfinished citation.
                break
            else:
                output.append(self.pending[0])
                self.pending = self.pending[1:]
        return "".join(output)


def frame(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
