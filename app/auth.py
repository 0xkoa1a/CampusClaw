import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from flask import (
    Blueprint,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db


bp = Blueprint("auth", __name__)
_DUMMY_HASH = generate_password_hash("invalid-password-for-timing")
TOKEN_TTL = 12 * 60 * 60
TOKEN_ISSUER = "campusclaw"
TOKEN_AUDIENCE = "campusclaw-api"


def _token_key():
    return hmac.digest(
        current_app.config["SECRET_KEY"].encode(), b"campusclaw-bearer-v1", hashlib.sha256
    )


def _issue_token(user_id, sid):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "jti": sid, "iat": now,
         "exp": now + timedelta(seconds=TOKEN_TTL),
         "iss": TOKEN_ISSUER, "aud": TOKEN_AUDIENCE},
        _token_key(), algorithm="HS256",
    )


@bp.before_app_request
def load_user():
    g.user = None
    g.auth_sid = None
    if request.endpoint == "health":
        return
    authorization = request.headers.get("Authorization")
    subject = None
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or len(token) > 4096:
            return
        try:
            claims = jwt.decode(
                token, _token_key(), algorithms=["HS256"],
                issuer=TOKEN_ISSUER, audience=TOKEN_AUDIENCE,
                options={"require": ["sub", "jti", "iat", "exp", "iss", "aud"]},
            )
        except jwt.InvalidTokenError:
            return
        sid, subject = claims["jti"], claims["sub"]
        if not isinstance(sid, str) or not isinstance(subject, str):
            return
    else:
        sid = session.get("sid")
    if not sid:
        return
    now = datetime.now(timezone.utc).isoformat()
    g.user = (
        get_db()
        .execute(
            "SELECT u.id,u.username,u.display_name,u.role,u.class_id,c.name AS class_name "
            "FROM sessions s JOIN users u ON u.id=s.user_id JOIN classes c ON c.id=u.class_id "
            "WHERE s.sid=? AND s.expires_at>?",
            (sid, now),
        )
        .fetchone()
    )
    if g.user is not None and subject is not None and str(g.user["id"]) != subject:
        g.user = None
    if g.user is not None:
        g.auth_sid = sid
    elif authorization is None:
        session.clear()


def require_user(page=False):
    if g.user is not None:
        return None
    if page:
        return redirect(url_for("auth.login_page"))
    return jsonify(error="请先登录"), 401


def _login(username, password):
    user = (
        get_db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    )
    valid = check_password_hash(
        user["password_hash"] if user else _DUMMY_HASH, password
    )
    if not user or not valid:
        return False
    old_sid = g.auth_sid or session.get("sid")
    new_sid = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    connection = get_db()
    with connection:
        if old_sid:
            connection.execute("DELETE FROM sessions WHERE sid=?", (old_sid,))
        connection.execute(
            "INSERT INTO sessions(sid,user_id,role,class_id,expires_at) VALUES (?,?,?,?,?)",
            (new_sid, user["id"], user["role"], user["class_id"], expires),
        )
    session.clear()
    session["sid"] = new_sid
    return user


@bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        if g.user:
            return redirect(url_for("materials.page"))
        return render_template("login.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if _login(username, password):
        return redirect(url_for("materials.page"))
    return render_template("login.html", error="账号或密码错误"), 401


@bp.post("/api/login")
def api_login():
    data = request.get_json(silent=True)
    if data is None:
        data = request.form
    if not hasattr(data, "get"):
        return jsonify(error="需要 JSON 对象"), 400
    mode = data.get("auth_mode", "cookie")
    if not isinstance(mode, str) or mode not in {"cookie", "bearer"}:
        return jsonify(error="不支持的认证方式"), 400
    user = _login(str(data.get("username", "")).strip(), str(data.get("password", "")))
    if user:
        payload = {"ok": True, "username": user["username"],
                   "role": user["role"], "class_id": user["class_id"]}
        if mode == "bearer":
            payload.update(access_token=_issue_token(user["id"], session["sid"]),
                           token_type="Bearer", expires_in=TOKEN_TTL)
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        return response
    return jsonify(error="账号或密码错误"), 401


@bp.post("/api/logout")
@bp.post("/logout")
def logout():
    if request.path == "/api/logout":
        denied = require_user()
        if denied:
            return denied
    sid = g.auth_sid or (session.get("sid") if request.headers.get("Authorization") is None else None)
    if sid:
        with get_db():
            get_db().execute("DELETE FROM sessions WHERE sid=?", (sid,))
    session.clear()
    if request.path == "/logout":
        return redirect(url_for("auth.login_page"))
    response = jsonify(ok=True)
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/api/me")
def me():
    denied = require_user()
    if denied:
        return denied
    return jsonify(
        id=g.user["id"],
        username=g.user["username"],
        role=g.user["role"],
        class_id=g.user["class_id"],
        class_name=g.user["class_name"],
    )
