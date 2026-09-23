import secrets
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
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


@bp.before_app_request
def load_user():
    g.user = None
    if request.endpoint == "health":
        return
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
    if g.user is None:
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
    old_sid = session.get("sid")
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
    return True


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
    data = request.get_json(silent=True) or request.form
    if _login(str(data.get("username", "")).strip(), str(data.get("password", ""))):
        return jsonify(ok=True)
    return jsonify(error="账号或密码错误"), 401


@bp.post("/api/logout")
@bp.post("/logout")
def logout():
    sid = session.get("sid")
    if sid:
        with get_db():
            get_db().execute("DELETE FROM sessions WHERE sid=?", (sid,))
    session.clear()
    if request.path == "/logout":
        return redirect(url_for("auth.login_page"))
    return jsonify(ok=True)


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
