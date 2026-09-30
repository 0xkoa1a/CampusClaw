"""Search, answer, and teacher reindex HTTP endpoints."""

import re

from flask import Blueprint, g, jsonify, request

from .auth import require_user
from .chunking import validate_strategy
from .db import get_db
from .gateway import GatewayUnavailable, chat_completion
from .indexing import index_material
from .retrieval import search
from .vector import VectorUnavailable


bp = Blueprint("search", __name__)
NO_EVIDENCE = "资料中未找到相关内容"
REFERENCE_RE = re.compile(r"\[(\d+)\]")


def _question(payload):
    question = payload.get("q")
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError("q 必须是非空且不超过 500 字的字符串")
    return question.strip()


@bp.post("/api/search")
def api_search():
    denied = require_user()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="需要 JSON 对象"), 400
    try:
        question = _question(payload)
        mode = payload.get("mode", "hybrid")
        limit = payload.get("limit", 10)
        offset = payload.get("offset", 0)
        if mode not in {"keyword", "vector", "hybrid"}:
            raise ValueError("mode 必须是 keyword、vector 或 hybrid")
        if type(limit) is not int or not 1 <= limit <= 30:
            raise ValueError("limit 必须在 1–30 之间")
        if type(offset) is not int or not 0 <= offset <= 1000:
            raise ValueError("offset 必须在 0–1000 之间")
        result = search(question, g.user["class_id"], mode, limit, offset)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except (GatewayUnavailable, VectorUnavailable) as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(mode=mode, **result)


@bp.post("/api/ask")
def api_ask():
    denied = require_user()
    if denied:
        return denied
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="需要 JSON 对象"), 400
    try:
        question = _question(payload)
        history = payload.get("history", [])
        if not isinstance(history, list) or len(history) > 12:
            raise ValueError("history 必须是不超过 12 条的数组")
        hits = search(question, g.user["class_id"], "hybrid", 4)["hits"]
        if not hits:
            return jsonify(answer=NO_EVIDENCE, citations=[])
        contexts = []
        for hit in hits:
            body = get_db().execute(
                "SELECT body FROM knowledge_chunks WHERE id=? AND class_id=?",
                (hit["chunk_id"], g.user["class_id"]),
            ).fetchone()["body"]
            contexts.append({**hit, "body": body})
        answer = chat_completion(question, contexts, history)
        answer = REFERENCE_RE.sub(
            lambda match: match.group() if 1 <= int(match.group(1)) <= len(hits) else "",
            answer,
        ).strip()
        references = sorted({int(number) for number in REFERENCE_RE.findall(answer)})
        if not references:
            answer += " [1]"
            references = [1]
        citations = [{"number": number, **hits[number - 1]} for number in references]
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except (GatewayUnavailable, VectorUnavailable) as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(answer=answer, citations=citations)


@bp.post("/api/materials/<int:material_id>/reindex")
def api_reindex(material_id):
    denied = require_user()
    if denied:
        return denied
    if g.user["role"] != "teacher":
        return jsonify(error="无管理权限"), 403
    row = get_db().execute(
        "SELECT id FROM materials WHERE id=? AND class_id=?",
        (material_id, g.user["class_id"]),
    ).fetchone()
    if row is None:
        return jsonify(error="材料不存在"), 404
    payload = request.get_json(silent=True) or {}
    try:
        strategy = validate_strategy(payload.get("strategy"))
        count = index_material(material_id, g.user["class_id"], strategy, replace=True)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except (GatewayUnavailable, VectorUnavailable) as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(status="ready", chunk_count=count)
