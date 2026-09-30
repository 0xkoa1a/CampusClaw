"""Synchronous index management for the single-instance course deployment."""

import uuid

from .chunking import split_text
from .db import get_db, insert_chunks
from .gateway import GatewayUnavailable, embed_texts
from .vector import VectorUnavailable, get_store


def _set_status(connection, material_id, status, error=None):
    with connection:
        connection.execute(
            "UPDATE materials SET index_status=?,index_error=? WHERE id=?",
            (status, error, material_id),
        )
        connection.execute(
            "UPDATE knowledge_chunks SET index_status=? WHERE material_id=?",
            (status, material_id),
        )


def index_material(material_id, class_id, strategy=None, replace=False):
    connection = get_db()
    material = connection.execute(
        """SELECT m.id,m.class_id,k.id AS knowledge_entry_id,k.body FROM materials m
           JOIN knowledge_entries k ON k.material_id=m.id
           WHERE m.id=? AND m.class_id=?""",
        (material_id, class_id),
    ).fetchone()
    if material is None:
        raise LookupError("材料不存在")
    old = connection.execute(
        "SELECT id,body,chunk_index FROM knowledge_chunks WHERE material_id=? ORDER BY chunk_index",
        (material_id,),
    ).fetchall()
    prepared = None
    if replace or not old:
        prepared = [(str(uuid.uuid4()), chunk) for chunk in split_text(material["body"], strategy)]
        records = [(chunk_id, chunk.body, index) for index, (chunk_id, chunk) in enumerate(prepared)]
    else:
        records = [(row["id"], row["body"], row["chunk_index"]) for row in old]
    if not records:
        _set_status(connection, material_id, "failed", "材料没有可索引文本")
        raise ValueError("材料没有可索引文本")
    store = get_store()
    try:
        vectors = embed_texts([body for _, body, _ in records])
        if len(vectors) != len(records):
            raise GatewayUnavailable("课程网关返回向量数量不正确")
        points = [
            {"id": chunk_id, "vector": vector, "payload": {
                "chunk_id": chunk_id, "class_id": class_id, "material_id": material_id,
                "knowledge_entry_id": material["knowledge_entry_id"], "chunk_index": index,
            }}
            for (chunk_id, _, index), vector in zip(records, vectors)
        ]
        store.upsert(points)
        if prepared is not None:
            with connection:
                connection.execute("DELETE FROM knowledge_chunks WHERE material_id=?", (material_id,))
                insert_chunks(connection, material_id, class_id, material["body"], strategy, prepared)
        if prepared is not None and old:
            store.delete([row["id"] for row in old])
        _set_status(connection, material_id, "ready")
        return len(records)
    except (GatewayUnavailable, VectorUnavailable, ValueError, OSError):
        _set_status(connection, material_id, "failed", "索引服务暂时不可用")
        raise
