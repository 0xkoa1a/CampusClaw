"""OpenAPI document generation for the application's API routes."""

from copy import deepcopy
import re

from flask import jsonify, render_template
from werkzeug.routing import IntegerConverter


def api_doc(operations: dict):
    """Attach OpenAPI operation dictionaries to a Flask view function."""
    if not isinstance(operations, dict):
        raise TypeError("api_doc operations must be a dictionary")

    def decorate(function):
        function._api_operations = deepcopy(operations)
        return function

    return decorate


ERROR_SCHEMA = {
    "type": "object",
    "properties": {"error": {"type": "string"}},
    "required": ["error"],
}


def json_schema(properties):
    """Build a small JSON object schema from a mapping of property schemas."""
    return {"type": "object", "properties": deepcopy(properties)}


STRING = {"type": "string"}
INTEGER = {"type": "integer"}
BOOLEAN = {"type": "boolean"}
STRING_ARRAY = {"type": "array", "items": STRING}
INTEGER_ARRAY = {"type": "array", "items": INTEGER}

IDENTITY_SCHEMA = json_schema({
    "id": INTEGER, "username": STRING,
    "role": {"type": "string", "enum": ["teacher", "student"]},
    "class_id": INTEGER, "class_name": STRING,
})
LOGIN_SCHEMA = json_schema({
    "ok": BOOLEAN, "username": STRING,
    "role": {"type": "string", "enum": ["teacher", "student"]},
    "class_id": INTEGER, "access_token": STRING,
    "token_type": {"type": "string", "enum": ["Bearer"]},
    "expires_in": INTEGER,
})
OK_SCHEMA = json_schema({"ok": BOOLEAN})
MATERIAL_SCHEMA = json_schema({
    "id": INTEGER, "title": STRING, "created_at": STRING,
    "index_status": {"type": "string", "enum": ["pending", "ready", "failed"]},
})
MATERIAL_DETAIL_SCHEMA = json_schema({
    **MATERIAL_SCHEMA["properties"], "body": STRING, "class_id": INTEGER,
})
MATERIAL_LIST_SCHEMA = json_schema({
    "materials": {"type": "array", "items": MATERIAL_SCHEMA},
})
MATERIAL_UPLOAD_SCHEMA = json_schema({
    "id": INTEGER,
    "index_status": {"type": "string", "enum": ["ready", "failed"]},
})
SEARCH_HIT_SCHEMA = json_schema({
    "chunk_id": STRING, "material_id": INTEGER, "title": STRING,
    "chunk_index": INTEGER, "start_offset": INTEGER, "end_offset": INTEGER,
    "heading": STRING, "excerpt": STRING, "source_url": STRING, "score": {"type": "number"},
})
SEARCH_SCHEMA = json_schema({
    "mode": {"type": "string", "enum": ["keyword", "vector", "hybrid"]},
    "hits": {"type": "array", "items": SEARCH_HIT_SCHEMA}, "total": INTEGER,
})
CITATION_SCHEMA = json_schema({"number": INTEGER, **SEARCH_HIT_SCHEMA["properties"]})
ASK_SCHEMA = json_schema({
    "answer": STRING, "citations": {"type": "array", "items": CITATION_SCHEMA},
})
REINDEX_SCHEMA = json_schema({"status": {"type": "string", "enum": ["ready"]}, "chunk_count": INTEGER})
SKILL_SCHEMA = json_schema({
    "id": INTEGER, "class_id": INTEGER, "name": STRING, "source_text": STRING,
    "trigger_text": STRING, "description": STRING, "subject_text": STRING,
    "enabled": BOOLEAN, "tools": STRING_ARRAY,
})
SKILL_LIST_SCHEMA = json_schema({"skills": {"type": "array", "items": SKILL_SCHEMA}})
SKILL_WRAPPER_SCHEMA = json_schema({"skill": SKILL_SCHEMA})
AGENT_SCHEMA = json_schema({
    "id": INTEGER, "class_id": INTEGER, "name": STRING, "role_prompt": STRING,
    "enabled": BOOLEAN, "skill_ids": INTEGER_ARRAY, "material_ids": INTEGER_ARRAY,
})
AGENT_LIST_SCHEMA = json_schema({"agents": {"type": "array", "items": AGENT_SCHEMA}})
AGENT_WRAPPER_SCHEMA = json_schema({"agent": AGENT_SCHEMA})
CONVERSATION_SCHEMA = json_schema({
    "id": INTEGER, "class_id": INTEGER, "user_id": INTEGER, "agent_id": INTEGER,
    "title": STRING, "created_at": STRING, "updated_at": STRING,
})
CONVERSATION_LIST_SCHEMA = json_schema({
    "conversations": {"type": "array", "items": CONVERSATION_SCHEMA},
})
MESSAGE_SCHEMA = json_schema({
    "id": INTEGER, "conversation_id": INTEGER,
    "role": {"type": "string", "enum": ["user", "assistant"]},
    "content": STRING,
    "citations": {"type": "array", "items": CITATION_SCHEMA},
    "skill_name": {"type": "string", "nullable": True},
    "status": {"type": "string", "enum": ["complete", "partial"]},
    "created_at": STRING,
})
CONVERSATION_DETAIL_SCHEMA = json_schema({
    "conversation": CONVERSATION_SCHEMA,
    "messages": {"type": "array", "items": MESSAGE_SCHEMA},
})
CONVERSATION_WRAPPER_SCHEMA = json_schema({"conversation": CONVERSATION_SCHEMA})


def _api_path(rule):
    """Translate Flask variable syntax and retain converter type information."""
    path = rule.rule
    parameters = []
    for argument, converter in rule._converters.items():
        schema = {"type": "integer"} if isinstance(converter, IntegerConverter) else {"type": "string"}
        parameters.append(
            {"name": argument, "in": "path", "required": True, "schema": schema}
        )
    path = re.sub(r"<(?:(?:[^:<>]+):)?([^<>]+)>", r"{\1}", path)
    return path, parameters


def _with_defaults(operation, path_parameters):
    result = deepcopy(operation)
    response_schema = result.pop("x-response-schema", None)
    success_status = result.pop("x-success-status", None)
    error_statuses = result.pop("x-error-statuses", [])
    if path_parameters:
        existing = result.get("parameters", [])
        known = {(item.get("in"), item.get("name")) for item in existing}
        result["parameters"] = existing + [
            item for item in path_parameters if ("path", item["name"]) not in known
        ]

    responses = result.setdefault("responses", {})
    error_descriptions = {
        "400": "Bad request", "403": "Forbidden", "404": "Not found",
        "409": "Conflict", "413": "Payload too large",
    }
    for status in error_statuses:
        status = str(status)
        if status not in error_descriptions:
            raise RuntimeError(f"Unsupported x-error-statuses value: {status}")
        responses.setdefault(status, {
            "description": error_descriptions[status],
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        })
    success_codes = [str(code) for code in responses if str(code).startswith("2")]
    if success_status is None:
        success_status = "201" if "201" in success_codes else "200"
    success_status = str(success_status)

    if not success_codes:
        response = {
            "description": "Successful response",
            "content": {
                "application/json": {
                    "schema": response_schema if response_schema is not None else {}
                }
            },
        }
        if success_status == "204":
            response.pop("content")
        responses[success_status] = response
    elif response_schema is not None:
        response = responses.get(success_status)
        if isinstance(response, dict):
            content = response.get("content", {})
            # An explicitly documented non-JSON representation is authoritative.
            if "application/json" in content:
                content["application/json"]["schema"] = response_schema
            elif not content:
                response["content"] = {
                    "application/json": {"schema": response_schema}
                }

    for status, description in (("401", "Unauthorized"), ("503", "Service unavailable")):
        responses.setdefault(
            status,
            {
                "description": description,
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
            },
        )
    for status, response in responses.items():
        if isinstance(response, dict):
            descriptions = {**error_descriptions, "401": "Unauthorized", "503": "Service unavailable"}
            response.setdefault("description", descriptions.get(str(status), "Response"))
            try:
                is_error = int(status) >= 400
            except (TypeError, ValueError):
                is_error = False
            if is_error and not response.get("content"):
                response["content"] = {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
    result.setdefault("security", [{"BearerAuth": []}])
    return result


def build_openapi_document(app):
    paths = {}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        view = app.view_functions[rule.endpoint]
        operations = getattr(view, "_api_operations", None)
        methods = sorted(set(rule.methods or ()) - {"HEAD", "OPTIONS"})
        path, parameters = _api_path(rule)
        for method in methods:
            operation = (operations or {}).get(method.lower())
            if operation is None:
                raise RuntimeError(
                    f"Missing api_doc for {method} {rule.rule} ({rule.endpoint})"
                )
            paths.setdefault(path, {})[method.lower()] = _with_defaults(operation, parameters)

    return {
        "openapi": "3.0.3",
        "info": {"title": "CampusClaw API", "version": "1.0.0"},
        "paths": paths,
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            },
            "schemas": {"Error": ERROR_SCHEMA},
        },
    }


def install_openapi(app):
    """Install same-origin OpenAPI JSON and Swagger UI routes."""
    document = build_openapi_document(app)

    @app.get("/openapi.json", endpoint="openapi_document")
    def openapi_document():
        return jsonify(document)

    @app.get("/swagger/", endpoint="swagger_ui")
    def swagger_ui():
        return render_template("swagger.html")
