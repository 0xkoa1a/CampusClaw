import os
import sqlite3
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
    app.config["DATABASE_PATH"] = str(Path(app.config["DATABASE_PATH"]).resolve())
    app.config["UPLOAD_DIR"] = str(Path(app.config["UPLOAD_DIR"]).resolve())

    db.init_app(app)

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

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder, "favicon.svg", mimetype="image/svg+xml"
        )

    from .auth import bp as auth_bp
    from .materials import bp as materials_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(materials_bp)
    return app
