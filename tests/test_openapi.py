import io
from pathlib import Path

import pytest
from flask import Flask

from app.openapi import api_doc, install_openapi, json_schema


STATIC_DIR = Path(__file__).parents[1] / "app" / "static"
TEMPLATE_DIR = Path(__file__).parents[1] / "app" / "templates"


def make_app(*, documented=True):
    app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)

    if documented:
        @app.get("/api/items/<int:item_id>")
        @api_doc({
            "get": {
                "summary": "Get an item",
                "responses": {"200": {"description": "Item returned"}},
            }
        })
        def get_item(item_id):
            return {"id": item_id}

        @app.post("/api/login")
        @api_doc({
            "post": {
                "summary": "Create a session",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "responses": {"200": {"description": "Session created"}},
                "security": [],
            }
        })
        def login():
            return {"ok": True}
    else:
        @app.get("/api/undocumented")
        def undocumented():
            return {"ok": True}

    install_openapi(app)
    return app


def test_openapi_converts_path_and_adds_shared_security_and_errors():
    app = make_app()
    document = app.test_client().get("/openapi.json").get_json()

    operation = document["paths"]["/api/items/{item_id}"]["get"]
    assert operation["summary"] == "Get an item"
    assert operation["parameters"] == [{
        "name": "item_id", "in": "path", "required": True,
        "schema": {"type": "integer"},
    }]
    assert operation["security"] == [{"BearerAuth": []}]
    assert "401" in operation["responses"] and "503" in operation["responses"]
    assert operation["responses"]["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Error"
    }
    assert document["openapi"] == "3.0.3"
    assert document["components"]["securitySchemes"]["BearerAuth"]["scheme"] == "bearer"


def test_login_can_disable_bearer_auth_and_retains_operation_metadata():
    document = make_app().test_client().get("/openapi.json").get_json()
    operation = document["paths"]["/api/login"]["post"]

    assert operation["security"] == []
    assert operation["requestBody"]["required"] is True
    assert operation["responses"]["200"]["description"] == "Session created"
    assert "403" not in operation["responses"]


def test_default_success_and_custom_201_schema():
    @api_doc({
        "get": {
            "summary": "List widgets",
            "x-response-schema": json_schema({"items": {"type": "array"}}),
        }
    })
    def listed():
        return {"items": []}

    @api_doc({
        "post": {
            "summary": "Create widget",
            "x-success-status": 201,
            "x-response-schema": json_schema({"id": {"type": "integer"}}),
        }
    })
    def created():
        return {"id": 1}, 201

    app = Flask(__name__)
    app.add_url_rule("/api/widgets", view_func=listed, methods=["GET"])
    app.add_url_rule("/api/widgets", view_func=created, methods=["POST"])
    install_openapi(app)
    paths = app.test_client().get("/openapi.json").get_json()["paths"]["/api/widgets"]

    get_operation = paths["get"]
    assert set(get_operation["responses"]) >= {"200", "401", "503"}
    assert get_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "type": "object", "properties": {"items": {"type": "array"}}
    }
    post_operation = paths["post"]
    assert "x-response-schema" not in post_operation
    assert "x-success-status" not in post_operation
    assert "200" not in post_operation["responses"]
    assert post_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "type": "object", "properties": {"id": {"type": "integer"}}
    }


def test_existing_success_responses_and_stream_or_binary_content_are_preserved():
    @api_doc({
        "get": {
            "summary": "Stream events",
            "x-response-schema": {"type": "object"},
            "responses": {
                "200": {
                    "description": "Event stream",
                    "content": {"text/event-stream": {"schema": {"type": "string"}}},
                },
                "204": {"description": "No content"},
            },
        }
    })
    def stream():
        return ""

    app = Flask(__name__)
    app.add_url_rule("/api/stream", view_func=stream, methods=["GET"])
    install_openapi(app)
    operation = app.test_client().get("/openapi.json").get_json()["paths"]["/api/stream"]["get"]

    assert "200" in operation["responses"] and "204" in operation["responses"]
    assert "text/event-stream" in operation["responses"]["200"]["content"]
    assert "application/json" not in operation["responses"]["200"]["content"]
    assert "content" not in operation["responses"]["204"]


def test_declared_conditional_error_codes_get_shared_error_schema():
    @api_doc({
        "get": {
            "summary": "Read protected item",
            "responses": {"400": {}, "403": {}, "404": {}},
        }
    })
    def read_item():
        return {}

    app = Flask(__name__)
    app.add_url_rule("/api/protected", view_func=read_item, methods=["GET"])
    install_openapi(app)
    document = app.test_client().get("/openapi.json").get_json()
    responses = document["paths"]["/api/protected"]["get"]["responses"]

    assert [responses[code]["description"] for code in ("400", "403", "404")] == [
        "Bad request", "Forbidden", "Not found"
    ]
    for code in ("400", "403", "404"):
        assert responses[code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/Error"
        }


def test_x_error_statuses_are_materialized_and_removed_from_operations():
    @api_doc({
        "post": {
            "summary": "Conditionally fails",
            "x-error-statuses": ["400", "403", "404", "409", "413"],
        }
    })
    def conditional():
        return {"ok": True}

    app = Flask(__name__)
    app.add_url_rule("/api/conditional", view_func=conditional, methods=["POST"])
    install_openapi(app)
    operation = app.test_client().get("/openapi.json").get_json()["paths"]["/api/conditional"]["post"]

    assert not any(key.startswith("x-") for key in operation)
    assert [operation["responses"][code]["description"] for code in ("400", "403", "404", "409", "413")] == [
        "Bad request", "Forbidden", "Not found", "Conflict", "Payload too large"
    ]


def test_missing_api_doc_fails_during_install():
    app = Flask(__name__)

    @app.get("/api/undocumented")
    def undocumented():
        return {"ok": True}

    with pytest.raises(RuntimeError, match="Missing api_doc for GET /api/undocumented"):
        install_openapi(app)


def test_swagger_serves_same_origin_page_and_official_assets():
    client = make_app().test_client()
    page = client.get("/swagger/")
    html = page.get_data(as_text=True)

    assert page.status_code == 200
    assert "validatorUrl: null" in html
    assert "persistAuthorization: false" in html
    assert "SwaggerUIBundle({" in html
    assert "validatorUrl: null" in html
    assert "/openapi.json" in html
    assert "https://" not in html and "http://" not in html
    assert client.get("/static/vendor/swagger/swagger-ui-bundle.js").status_code == 200
    assert client.get("/static/vendor/swagger/swagger-ui.css").status_code == 200
    assert (STATIC_DIR / "vendor/swagger/LICENSE").is_file()


def _resolve_schema(schema, document):
    reference = schema.get("$ref")
    if reference:
        _, _, pointer = reference.partition("#/components/schemas/")
        return document["components"]["schemas"][pointer]
    return schema


def _assert_payload_matches(schema, value, document):
    schema = _resolve_schema(schema, document)
    schema_type = schema.get("type")
    if value is None and schema.get("nullable"):
        return
    if schema_type == "object":
        assert isinstance(value, dict)
        properties = schema.get("properties", {})
        assert set(value) <= set(properties)
        for name, item in value.items():
            _assert_payload_matches(properties[name], item, document)
    elif schema_type == "array":
        assert isinstance(value, list)
        for item in value:
            _assert_payload_matches(schema["items"], item, document)
    elif schema_type == "string":
        assert isinstance(value, str)
    elif schema_type == "integer":
        assert type(value) is int
    elif schema_type == "boolean":
        assert type(value) is bool
    elif schema_type == "number":
        assert type(value) in (int, float)


def _assert_documented_json(document, path, method, response):
    operation = document["paths"][path][method]
    response_doc = operation["responses"][str(response.status_code)]
    schema = response_doc["content"]["application/json"]["schema"]
    _assert_payload_matches(schema, response.get_json(), document)


def test_main_app_documents_every_api_success_and_matches_real_json_responses(
    app, client, monkeypatch
):
    document = client.get("/openapi.json").get_json()
    for path, path_item in document["paths"].items():
        for method, operation in path_item.items():
            successes = [
                (status, response)
                for status, response in operation["responses"].items()
                if status.startswith("2")
            ]
            assert successes, f"{method.upper()} {path} has no success response"
            assert not {"x-response-schema", "x-success-status", "x-error-statuses"} & set(operation)
            for status, response in successes:
                if status == "204":
                    assert "content" not in response
                else:
                    assert response.get("content"), f"{method.upper()} {path} has no success content"
                    for media_type, media in response["content"].items():
                        assert "schema" in media, f"{method.upper()} {path} {status} {media_type} has no schema"

    assert "403" not in document["paths"]["/api/login"]["post"]["responses"]

    login_response = client.post(
        "/api/login", json={"username": "teacher_a", "password": "teacher-test-password", "auth_mode": "bearer"}
    )
    assert login_response.status_code == 200
    _assert_documented_json(document, "/api/login", "post", login_response)
    me_response = client.get("/api/me")
    _assert_documented_json(document, "/api/me", "get", me_response)

    materials_response = client.get("/api/materials")
    _assert_documented_json(document, "/api/materials", "get", materials_response)
    material_id = materials_response.json["materials"][0]["id"]
    detail_response = client.get(f"/api/materials/{material_id}")
    _assert_documented_json(document, "/api/materials/{material_id}", "get", detail_response)

    monkeypatch.setattr("app.materials.index_material", lambda *_args, **_kwargs: 1)
    upload_response = client.post(
        "/api/materials",
        data={"file": (io.BytesIO(b"OpenAPI response schema fixture."), "schema.txt")},
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201
    _assert_documented_json(document, "/api/materials", "post", upload_response)
    uploaded_id = upload_response.json["id"]
    file_response = client.get(f"/api/materials/{uploaded_id}/file")
    assert file_response.status_code == 200
    file_schema = document["paths"]["/api/materials/{material_id}/file"]["get"]["responses"]["200"]["content"]["application/octet-stream"]["schema"]
    assert file_schema == {"type": "string", "format": "binary"}

    hit = {
        "chunk_id": "fixture-chunk", "material_id": uploaded_id, "title": "schema.txt",
        "chunk_index": 0, "start_offset": 0, "end_offset": 10, "heading": "",
        "excerpt": "OpenAPI response schema fixture.",
        "source_url": f"/materials?id={uploaded_id}&chunk=fixture-chunk#source", "score": 0.75,
    }
    monkeypatch.setattr("app.search.search", lambda *_args, **_kwargs: {"hits": [hit], "total": 1})
    search_response = client.post("/api/search", json={"q": "schema", "mode": "keyword"})
    _assert_documented_json(document, "/api/search", "post", search_response)
    monkeypatch.setattr("app.search.search", lambda *_args, **_kwargs: {"hits": [], "total": 0})
    ask_response = client.post("/api/ask", json={"q": "schema"})
    _assert_documented_json(document, "/api/ask", "post", ask_response)
    monkeypatch.setattr("app.search.index_material", lambda *_args, **_kwargs: 2)
    reindex_response = client.post(f"/api/materials/{material_id}/reindex", json={})
    _assert_documented_json(document, "/api/materials/{material_id}/reindex", "post", reindex_response)

    def skill_source(name):
        return f"名称：{name}\n适用条件：schema\n工具：knowledge_search\n启用：是\n\n返回清晰说明。"

    skill_create = client.post("/api/skills", json={"source": skill_source("Schema skill")})
    _assert_documented_json(document, "/api/skills", "post", skill_create)
    skill_id = skill_create.json["skill"]["id"]
    skill_list = client.get("/api/skills")
    _assert_documented_json(document, "/api/skills", "get", skill_list)
    skill_get = client.get(f"/api/skills/{skill_id}")
    _assert_documented_json(document, "/api/skills/{identifier}", "get", skill_get)
    skill_update = client.put(f"/api/skills/{skill_id}", json={"source": skill_source("Schema skill")})
    _assert_documented_json(document, "/api/skills/{identifier}", "put", skill_update)

    agent_create = client.post("/api/agents", json={
        "name": "Schema agent", "role_prompt": "Explain clearly", "enabled": True,
        "skill_ids": [skill_id], "material_ids": [uploaded_id],
    })
    _assert_documented_json(document, "/api/agents", "post", agent_create)
    agent_id = agent_create.json["agent"]["id"]
    _assert_documented_json(document, "/api/agents", "get", client.get("/api/agents"))
    _assert_documented_json(document, "/api/agents/{identifier}", "get", client.get(f"/api/agents/{agent_id}"))
    agent_update = client.put(f"/api/agents/{agent_id}", json={"name": "Schema agent updated"})
    _assert_documented_json(document, "/api/agents/{identifier}", "put", agent_update)

    conversation_create = client.post("/api/conversations", json={"agent_id": agent_id})
    _assert_documented_json(document, "/api/conversations", "post", conversation_create)
    conversation_id = conversation_create.json["conversation"]["id"]
    _assert_documented_json(document, "/api/conversations", "get", client.get("/api/conversations"))
    monkeypatch.setattr("app.conversations.search", lambda *_args, **_kwargs: {"hits": []})
    monkeypatch.setattr(
        "app.conversations.chat_stream",
        lambda *_args, **_kwargs: (piece for piece in ["A concise answer."]),
    )
    sse_response = client.post(
        f"/api/conversations/{conversation_id}/messages", json={"content": "Explain this"}
    )
    assert sse_response.status_code == 200
    assert sse_response.mimetype == "text/event-stream"
    assert "event: done" in sse_response.get_data(as_text=True)
    sse_schema = document["paths"]["/api/conversations/{identifier}/messages"]["post"]["responses"]["200"]["content"]
    assert set(sse_schema) == {"text/event-stream"}
    conversation_detail = client.get(f"/api/conversations/{conversation_id}")
    _assert_documented_json(document, "/api/conversations/{identifier}", "get", conversation_detail)
    assert conversation_detail.json["messages"][-1]["status"] == "complete"
    conversation_delete = client.delete(f"/api/conversations/{conversation_id}")
    assert conversation_delete.status_code == 204
    skill_delete = client.delete(f"/api/skills/{skill_id}")
    assert skill_delete.status_code == 204

    logout_response = client.post("/api/logout")
    _assert_documented_json(document, "/api/logout", "post", logout_response)
