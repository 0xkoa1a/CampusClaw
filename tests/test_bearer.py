import io
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.auth import _token_key, TOKEN_AUDIENCE, TOKEN_ISSUER
from app.db import connect
from conftest import login


def bearer_login(client, username="teacher_a", password="teacher-test-password"):
    return client.post("/api/login", json={
        "username": username, "password": password, "auth_mode": "bearer",
        "role": "teacher", "class_id": 2,
    })


def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("username,password,role,class_id", [
    ("teacher_a", "teacher-test-password", "teacher", 1),
    ("student_a1", "student-a-test-password", "student", 1),
    ("student_b1", "student-b-test-password", "student", 2),
])
def test_bearer_without_cookie(app, username, password, role, class_id):
    client = app.test_client(use_cookies=False)
    response = bearer_login(client, username, password)
    assert response.status_code == 200
    assert response.json["token_type"] == "Bearer"
    assert response.json["expires_in"] == 43200
    assert response.headers["Cache-Control"] == "no-store"
    assert "password_hash" not in response.get_data(as_text=True)
    auth = headers(response.json["access_token"])
    me = client.get("/api/me", headers=auth)
    assert (me.json["role"], me.json["class_id"]) == (role, class_id)
    assert client.get("/api/materials", headers=auth).status_code == 200


def test_bearer_revocation_and_cookie_compatibility(app):
    client = app.test_client()
    response = bearer_login(client)
    auth = headers(response.json["access_token"])
    cookie = client.get_cookie("session").value
    assert client.get("/materials").status_code == 200
    assert client.post("/api/logout", headers=auth).status_code == 200
    client.set_cookie("session", cookie)
    assert client.get("/api/me", headers=auth).status_code == 401
    assert client.get("/api/me").status_code == 401
    assert login(client).status_code == 200
    assert client.get("/api/me").status_code == 200


def test_bearer_class_and_role(app):
    client = app.test_client(use_cookies=False)
    auth = headers(bearer_login(client, "student_a1", "student-a-test-password").json["access_token"])
    assert client.get("/api/materials?class_id=2&role=teacher", headers=auth).json["materials"][0]["title"] == "A 班入门讲义"
    assert client.get("/api/materials/2/file", headers=auth).status_code == 404
    assert client.get("/api/materials/2", headers=auth).status_code == 404
    response = client.post("/api/materials", headers=auth, data={
        "role": "teacher", "class_id": "2", "file": (io.BytesIO(b"hello"), "test.md"),
    })
    assert response.status_code == 403
    assert client.post("/api/materials/1/reindex", headers=auth, json={}).status_code == 403


@pytest.mark.parametrize("mutation", ["signature", "expired", "issuer", "audience", "missing", "subject", "algorithm"])
def test_invalid_bearer_never_falls_back(app, client, mutation):
    token = bearer_login(client).json["access_token"]
    with app.app_context():
        key = _token_key()
    payload = jwt.decode(token, key, algorithms=["HS256"], audience=TOKEN_AUDIENCE, issuer=TOKEN_ISSUER)
    algorithm = "HS256"
    if mutation == "signature":
        token = jwt.encode(payload, b"different-test-key-of-at-least-32-bytes", algorithm=algorithm)
    else:
        if mutation == "expired":
            payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=5)
        elif mutation == "issuer":
            payload["iss"] = "other"
        elif mutation == "audience":
            payload["aud"] = "other"
        elif mutation == "missing":
            del payload["exp"]
        elif mutation == "subject":
            payload["sub"] = "2"
        elif mutation == "algorithm":
            algorithm = "HS384"
            key = key + b"test-only-padding"
        token = jwt.encode(payload, key, algorithm=algorithm)
    assert client.get("/api/me").status_code == 200
    assert client.get("/api/materials", headers=headers(token)).status_code == 401
    assert client.post("/api/logout", headers=headers(token)).status_code == 401
    assert client.get("/api/me").status_code == 200


@pytest.mark.parametrize("authorization", ["Bearer", "Basic invalid", "Bearer invalid", ""])
def test_malformed_authorization(client, authorization):
    login(client)
    assert client.get("/api/me", headers={"Authorization": authorization}).status_code == 401


def test_server_session_expiry(app, client):
    auth = headers(bearer_login(client).json["access_token"])
    connection = connect(app.config["DATABASE_PATH"])
    try:
        with connection:
            connection.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    finally:
        connection.close()
    assert client.get("/api/me", headers=auth).status_code == 401


def test_no_token_for_bad_password_or_mode(client):
    response = bearer_login(client, password="wrong")
    assert response.status_code == 401 and "access_token" not in response.json
    for payload in ({"auth_mode": "other"}, {"auth_mode": []}, []):
        assert client.post("/api/login", json=payload).status_code == 400
    assert client.get("/api/me").status_code == 401


def test_form_login_works_without_javascript(client):
    response = client.post("/login", data={"username": "teacher_a", "password": "teacher-test-password"})
    assert response.status_code == 302
    assert client.get("/materials").status_code == 200
