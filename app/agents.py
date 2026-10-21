"""Teacher-managed configuration; authorization always uses the authenticated user."""

from flask import Blueprint, g, jsonify, request

from .auth import require_user
from .db import get_db
from .agent_store import ApiProblem, owned_row, skill_json, agent_json, save_agent, save_skill
from .openapi import (
    AGENT_LIST_SCHEMA, AGENT_WRAPPER_SCHEMA, SKILL_LIST_SCHEMA,
    SKILL_WRAPPER_SCHEMA, api_doc,
)

bp = Blueprint("agents", __name__)


@bp.errorhandler(ApiProblem)
def problem(error):
    return jsonify(error=str(error)), error.status


def permission(write=False):
    denied = require_user()
    if denied:
        return denied
    if write and g.user["role"] != "teacher":
        return jsonify(error="需要教师权限"), 403


@bp.route("/api/skills", methods=["GET", "POST"])
@api_doc({"get": {"summary": "列出本班技能", "x-response-schema": SKILL_LIST_SCHEMA}, "post": {"summary": "教师创建技能", "x-response-schema": SKILL_WRAPPER_SCHEMA, "x-error-statuses": ["400", "403"], "responses": {"201": {"description": "已创建"}}, "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["source"], "properties": {"source": {"type": "string", "maxLength": 8000}}}}}}}})
def skills():
    denied = permission(request.method == "POST")
    if denied:
        return denied
    if request.method == "GET":
        return jsonify(skills=[skill_json(row) for row in get_db().execute("SELECT * FROM skills WHERE class_id=? ORDER BY id", (g.user["class_id"],))])
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiProblem("需要JSON对象")
    return jsonify(skill=save_skill(g.user["class_id"], payload.get("source"))), 201


@bp.route("/api/skills/<int:identifier>", methods=["GET", "PUT", "DELETE"])
@api_doc({"get": {"summary": "读取本班技能", "x-response-schema": SKILL_WRAPPER_SCHEMA, "x-error-statuses": ["404"]}, "put": {"summary": "教师更新技能原文", "x-response-schema": SKILL_WRAPPER_SCHEMA, "x-error-statuses": ["400", "403", "404"], "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["source"], "properties": {"source": {"type": "string", "maxLength": 8000}}}}}}}, "delete": {"summary": "教师删除技能", "x-error-statuses": ["403", "404"], "responses": {"204": {"description": "已删除"}}}})
def skill(identifier):
    denied = permission(request.method != "GET")
    if denied:
        return denied
    row = owned_row("skills", identifier, g.user["class_id"])
    if request.method == "GET":
        return jsonify(skill=skill_json(row))
    if request.method == "DELETE":
        with get_db():
            get_db().execute("DELETE FROM skills WHERE id=? AND class_id=?", (identifier, g.user["class_id"]))
        return "", 204
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiProblem("需要JSON对象")
    return jsonify(skill=save_skill(g.user["class_id"], payload.get("source"), identifier))


AGENT_BODY = {"required": True, "content": {"application/json": {"schema": {
    "type": "object", "properties": {
        "name": {"type": "string", "maxLength": 64}, "role_prompt": {"type": "string", "maxLength": 2000},
        "enabled": {"type": "boolean"}, "skill_ids": {"type": "array", "items": {"type": "integer"}},
        "material_ids": {"type": "array", "items": {"type": "integer"}},
        "tool_names": {"type": "array", "items": {"type": "string", "enum": ["calculator"]}},
    },
}}}}


@bp.route("/api/agents", methods=["GET", "POST"])
@api_doc({"get": {"summary": "列出本班智能体，学生只见启用项", "x-response-schema": AGENT_LIST_SCHEMA}, "post": {"summary": "教师创建智能体", "x-response-schema": AGENT_WRAPPER_SCHEMA, "x-error-statuses": ["400", "403", "404"], "requestBody": AGENT_BODY, "responses": {"201": {"description": "已创建"}}}})
def agents():
    denied = permission(request.method == "POST")
    if denied:
        return denied
    if request.method == "GET":
        query = "SELECT * FROM agents WHERE class_id=?" + (" AND enabled=1" if g.user["role"] == "student" else "") + " ORDER BY id"
        return jsonify(agents=[agent_json(row) for row in get_db().execute(query, (g.user["class_id"],))])
    return jsonify(agent=save_agent(g.user["class_id"], request.get_json(silent=True))), 201


@bp.route("/api/agents/<int:identifier>", methods=["GET", "PUT"])
@api_doc({"get": {"summary": "读取本班智能体", "x-response-schema": AGENT_WRAPPER_SCHEMA, "x-error-statuses": ["404"]}, "put": {"summary": "教师更新智能体与绑定", "x-response-schema": AGENT_WRAPPER_SCHEMA, "x-error-statuses": ["400", "403", "404"], "requestBody": AGENT_BODY}})
def agent(identifier):
    denied = permission(request.method == "PUT")
    if denied:
        return denied
    row = owned_row("agents", identifier, g.user["class_id"])
    if request.method == "GET":
        if g.user["role"] == "student" and not row["enabled"]:
            from .agent_store import missing
            raise missing()
        return jsonify(agent=agent_json(row))
    return jsonify(agent=save_agent(g.user["class_id"], request.get_json(silent=True), identifier))
