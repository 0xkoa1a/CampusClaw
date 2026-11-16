import os
import sqlite3
import threading
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from . import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE_PATH=os.environ.get("DATABASE_PATH", "data/campusclaw.sqlite3"),
        UPLOAD_DIR=os.environ.get("UPLOAD_DIR", "uploads"),
        SEED_TEACHER_PASSWORD=os.environ.get("SEED_TEACHER_PASSWORD"),
        SEED_STUDENT_A_PASSWORD=os.environ.get("SEED_STUDENT_A_PASSWORD"),
        SEED_STUDENT_B_PASSWORD=os.environ.get("SEED_STUDENT_B_PASSWORD"),
        MAX_UPLOAD_BYTES=int(os.environ.get("MAX_UPLOAD_BYTES", "1048576")),
        EMBEDDING_BASE_URL=os.environ.get("EMBEDDING_BASE_URL", ""),
        EMBEDDING_API_KEY=os.environ.get("EMBEDDING_API_KEY", ""),
        EMBEDDING_MODEL=os.environ.get("EMBEDDING_MODEL", "course-embedding"),
        EMBEDDING_DIM=int(os.environ.get("EMBEDDING_DIM", "2048")),
        CHAT_MODEL=os.environ.get("CHAT_MODEL", "course-chat"),
        MCP_AUTH_TOKEN=os.environ.get("MCP_AUTH_TOKEN", ""),
        MCP_MAX_ROUNDS=int(os.environ.get("MCP_MAX_ROUNDS", "2")),
        MCP_MAX_CALLS=int(os.environ.get("MCP_MAX_CALLS", "4")),
        MCP_TOOL_TEXT_MAX_CHARS=int(os.environ.get("MCP_TOOL_TEXT_MAX_CHARS", "4000")),
        TASK_MAX_ATTEMPTS=int(os.environ.get('TASK_MAX_ATTEMPTS', '3')),
        TASK_LEASE_SECONDS=int(os.environ.get('TASK_LEASE_SECONDS', '120')),
        TASK_RETRY_BASE_SECONDS=float(os.environ.get('TASK_RETRY_BASE_SECONDS', '1')),
        TASK_QUEUE_NAME=os.environ.get('TASK_QUEUE_NAME', 'campusclaw.grading.v1'),
        RABBITMQ_URL=os.environ.get('RABBITMQ_URL', ''),
        MCP_ALLOWED_BASE_URLS=os.environ.get("MCP_ALLOWED_BASE_URLS", "http://mcp-demo:8090").split(","),
        AI_TIMEOUT_SECONDS=int(os.environ.get("AI_TIMEOUT_SECONDS", "30")),
        QDRANT_URL=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        QDRANT_COLLECTION=os.environ.get("QDRANT_COLLECTION", "campusclaw_chunks"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
        MAX_CONTENT_LENGTH=int(os.environ.get("MAX_UPLOAD_BYTES", "1048576")) + 16384,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY is required")
    if app.config["MAX_UPLOAD_BYTES"] <= 0:
        raise RuntimeError("MAX_UPLOAD_BYTES must be positive")
    for name, low, high in (("MCP_MAX_ROUNDS", 1, 8), ("MCP_MAX_CALLS", 1, 32),
                            ("MCP_TOOL_TEXT_MAX_CHARS", 128, 16000), ('TASK_MAX_ATTEMPTS', 1, 10),
                            ('TASK_LEASE_SECONDS', 10, 3600)):
        value = app.config[name]
        if type(value) is not int or not low <= value <= high:
            raise RuntimeError(f"{name} must be an integer between {low} and {high}")
    value = app.config['TASK_RETRY_BASE_SECONDS']
    if type(value) not in (int, float) or not .001 <= value <= 60:
        raise RuntimeError('TASK_RETRY_BASE_SECONDS must be between .001 and 60')
    if not app.config['RABBITMQ_URL'] and os.environ.get('RABBITMQ_PASSWORD'):
        from urllib.parse import quote
        user = quote(os.environ.get('RABBITMQ_USER', 'campusclaw'), safe='')
        password = quote(os.environ['RABBITMQ_PASSWORD'], safe='')
        host = os.environ.get('RABBITMQ_HOST', 'rabbitmq')
        app.config['RABBITMQ_URL'] = f'amqp://{user}:{password}@{host}:5672/%2F'
    app.config["DATABASE_PATH"] = str(Path(app.config["DATABASE_PATH"]).resolve())
    app.config["UPLOAD_DIR"] = str(Path(app.config["UPLOAD_DIR"]).resolve())

    db.init_app(app)
    from .observability import init_observability
    init_observability(app)

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_error):
        return jsonify(error="文件超过大小限制"), 413

    @app.errorhandler(sqlite3.Error)
    def database_unavailable(error):
        app.logger.error("database unavailable: %s", error)
        if request.path.startswith("/api/"):
            return jsonify(error="服务暂时不可用"), 503
        return "服务暂时不可用", 503

    @app.get("/")
    def index():
        return redirect(
            url_for("materials.page" if session.get("sid") else "auth.login_page")
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get('/ready')
    def ready():
        try:
            db.get_db().execute('SELECT 1 FROM users LIMIT 1').fetchone()
        except sqlite3.Error:
            return jsonify(status='unavailable'), 503
        return jsonify(status='ready')

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder, "favicon.svg", mimetype="image/svg+xml"
        )

    from .auth import bp as auth_bp
    from .materials import bp as materials_bp
    from .search import bp as search_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(search_bp)
    from .agents import bp as agents_bp
    from .conversations import bp as conversations_bp
    from .openapi import install_openapi
    app.extensions["conversation_locks"] = {"guard": threading.Lock(), "locks": {}}
    app.register_blueprint(agents_bp)
    app.register_blueprint(conversations_bp)
    from .assignments import bp as assignments_bp
    app.register_blueprint(assignments_bp)
    from .mcp_registry import bp as mcp_bp
    app.register_blueprint(mcp_bp)
    @app.get("/mcp")
    def mcp_page():
        from .auth import require_user
        from flask import g, render_template
        denied = require_user(page=True)
        if denied:
            return denied
        if g.user["role"] != "teacher":
            return "需要教师权限", 403
        return render_template("mcp.html")
    from .security import init_security
    init_security(app)
    from .monitoring import bp as monitoring_bp
    app.register_blueprint(monitoring_bp)
    from .observability import bp as audit_bp
    app.register_blueprint(audit_bp)
    install_openapi(app)
    return app
