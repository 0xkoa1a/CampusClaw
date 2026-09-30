import logging
import sqlite3
import uuid
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    jsonify,
    render_template,
    request,
    send_file,
)

from .auth import require_user
from .db import get_db, list_materials, material_with_body
from .indexing import index_material
from .gateway import GatewayUnavailable
from .knowledge import parse_text
from .vector import VectorUnavailable
from .db import insert_chunks


bp = Blueprint("materials", __name__)


def _visible_material(material_id):
    row = material_with_body(material_id)
    if row is None or row["class_id"] != g.user["class_id"]:
        if row is not None:
            logging.info(
                "cross-class material request: user=%s material=%s",
                g.user["id"],
                material_id,
            )
        return None
    return row


@bp.get("/materials")
def page():
    denied = require_user(page=True)
    if denied:
        return denied
    rows = list_materials(g.user["class_id"])
    selected_id = request.args.get("id", type=int)
    selected = _visible_material(selected_id) if selected_id else None
    if selected_id and selected is None:
        abort(404)
    if selected is None and rows:
        selected = _visible_material(rows[0]["id"])
    highlight = None
    chunk_id = request.args.get("chunk")
    if selected is not None and chunk_id:
        chunk = get_db().execute(
            """SELECT start_offset,end_offset FROM knowledge_chunks
               WHERE id=? AND material_id=? AND class_id=?""",
            (chunk_id, selected["id"], g.user["class_id"]),
        ).fetchone()
        if chunk:
            highlight = (
                selected["body"][: chunk["start_offset"]],
                selected["body"][chunk["start_offset"] : chunk["end_offset"]],
                selected["body"][chunk["end_offset"] :],
            )
    return render_template(
        "materials.html",
        rows=rows,
        selected=selected,
        highlight=highlight,
        max_upload=current_app.config["MAX_UPLOAD_BYTES"],
    )


@bp.get("/api/materials")
def api_list():
    denied = require_user()
    if denied:
        return denied
    return jsonify(materials=[dict(row) for row in list_materials(g.user["class_id"])])


@bp.get("/api/materials/<int:material_id>")
def api_detail(material_id):
    denied = require_user()
    if denied:
        return denied
    row = _visible_material(material_id)
    if row is None:
        return jsonify(error="材料不存在"), 404
    return jsonify(
        id=row["id"],
        title=row["title"],
        body=row["body"],
        class_id=row["class_id"],
        created_at=row["created_at"],
        index_status=row["index_status"],
    )


@bp.get("/api/materials/<int:material_id>/file")
def api_file(material_id):
    denied = require_user()
    if denied:
        return denied
    row = _visible_material(material_id)
    if row is None or not row["stored_name"]:
        return jsonify(error="材料不存在"), 404
    path = (
        Path(current_app.config["UPLOAD_DIR"])
        / str(row["class_id"])
        / row["stored_name"]
    )
    if not path.is_file():
        return jsonify(error="材料不存在"), 404
    return send_file(path, as_attachment=True, download_name=row["original_name"])


@bp.post("/api/materials")
def api_upload():
    denied = require_user()
    if denied:
        return denied
    if g.user["role"] != "teacher":
        return jsonify(error="无上传权限"), 403
    incoming = request.files.get("file")
    if not incoming or not incoming.filename:
        return jsonify(error="请选择文件"), 400
    original_name = incoming.filename.replace("\\", "/").split("/")[-1]
    extension = Path(original_name).suffix.lower()
    if extension not in {".txt", ".md"}:
        return jsonify(error="仅支持 .txt 或 .md"), 400
    limit = current_app.config["MAX_UPLOAD_BYTES"]
    raw = incoming.stream.read(limit + 1)
    if len(raw) > limit:
        return jsonify(error="文件超过大小限制"), 413
    try:
        body = parse_text(raw)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    class_id = g.user["class_id"]
    directory = Path(current_app.config["UPLOAD_DIR"]) / str(class_id)
    directory.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    path = directory / stored_name
    try:
        with path.open("xb") as output:
            output.write(raw)
        connection = get_db()
        with connection:
            material_id = connection.execute(
                "INSERT INTO materials(class_id,teacher_id,title,stored_name,original_name) VALUES (?,?,?,?,?)",
                (class_id, g.user["id"], original_name, stored_name, original_name),
            ).lastrowid
            connection.execute(
                "INSERT INTO knowledge_entries(material_id,class_id,body) VALUES (?,?,?)",
                (material_id, class_id, body),
            )
            insert_chunks(connection, material_id, class_id, body)
    except (OSError, sqlite3.Error):
        path.unlink(missing_ok=True)
        current_app.logger.exception("material upload failed")
        return jsonify(error="上传失败"), 500
    try:
        index_material(material_id, class_id)
        status = "ready"
    except (GatewayUnavailable, VectorUnavailable, ValueError):
        current_app.logger.warning("material %s uploaded but vector indexing failed", material_id)
        status = "failed"
    return jsonify(id=material_id, index_status=status), 201
