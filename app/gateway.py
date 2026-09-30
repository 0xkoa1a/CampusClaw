"""Small OpenAI-compatible client for the course gateway."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app


class GatewayUnavailable(RuntimeError):
    pass


def _post(path, payload):
    base = current_app.config["EMBEDDING_BASE_URL"].rstrip("/")
    key = current_app.config["EMBEDDING_API_KEY"]
    if not base or not key:
        raise GatewayUnavailable("课程网关尚未配置")
    request = Request(
        base + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=current_app.config["AI_TIMEOUT_SECONDS"]) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise GatewayUnavailable("课程网关暂时不可用") from exc


def embed_texts(texts):
    provider = current_app.config.get("EMBEDDING_PROVIDER")
    if provider is not None:
        return provider(texts)
    if not texts:
        return []
    vectors = []
    for begin in range(0, len(texts), 16):
        batch = texts[begin : begin + 16]
        data = _post("/embeddings", {
            "model": current_app.config["EMBEDDING_MODEL"], "input": batch,
        })
        try:
            ordered = sorted(data["data"], key=lambda item: item["index"])
            result = [item["embedding"] for item in ordered]
            if len(result) != len(batch) or any(
                len(vector) != current_app.config["EMBEDDING_DIM"] for vector in result
            ):
                raise ValueError("embedding dimension mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            raise GatewayUnavailable("课程网关返回的向量格式或维度不正确") from exc
        vectors.extend(result)
    return vectors


def chat_completion(question, contexts, history=None):
    provider = current_app.config.get("CHAT_PROVIDER")
    if provider is not None:
        return provider(question, contexts, history or [])
    messages = [{
        "role": "system",
        "content": "你是课程资料问答助手。只依据编号资料回答，简短作答，并使用[1]等编号标明依据。资料不足时明确说资料中未找到相关内容。不要编造来源。",
    }]
    for item in (history or [])[-6:]:
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and isinstance(item.get("content"), str):
            messages.append({"role": item["role"], "content": item["content"][:2000]})
    excerpts = "\n\n".join(
        f"[{number}] {item['title']} · 切片 {item['chunk_index'] + 1}：{item['body']}"
        for number, item in enumerate(contexts, 1)
    )
    messages.append({"role": "user", "content": f"资料：\n{excerpts}\n\n问题：{question}"})
    data = _post("/chat/completions", {
        "model": current_app.config["CHAT_MODEL"], "messages": messages,
        "temperature": 0.2, "max_tokens": 450,
    })
    try:
        answer = data["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("empty answer")
        return answer.strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise GatewayUnavailable("课程网关未返回有效回答") from exc
