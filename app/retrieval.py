"""Class-scoped keyword, vector, and reciprocal-rank-fusion retrieval."""

from .chunking import terms
from .db import get_db
from .gateway import embed_texts
from .vector import get_store


def _hit(row, score):
    return {
        "chunk_id": row["id"], "material_id": row["material_id"],
        "title": row["title"], "chunk_index": row["chunk_index"],
        "start_offset": row["start_offset"], "end_offset": row["end_offset"],
        "heading": row["heading"], "excerpt": row["body"][:300],
        "source_url": f"/materials?id={row['material_id']}&chunk={row['id']}#source",
        "score": round(float(score), 5),
    }


def keyword_search(question, class_id, limit=100, material_ids=None):
    if material_ids == []:
        return []
    query_terms = list(terms(question))
    if not query_terms:
        return []
    placeholders = ",".join("?" for _ in query_terms)
    scope = "" if material_ids is None else " AND m.id IN (" + ",".join("?" for _ in material_ids) + ")"
    rows = get_db().execute(
        f"""SELECT c.*,m.title,SUM(t.frequency) AS rank_score
            FROM chunk_terms t JOIN knowledge_chunks c ON c.id=t.chunk_id
            JOIN materials m ON m.id=c.material_id
            WHERE t.class_id=? AND c.class_id=? AND m.class_id=?
              AND t.term IN ({placeholders})
              {scope}
            GROUP BY c.id ORDER BY rank_score DESC,c.material_id,c.chunk_index LIMIT ?""",
        (class_id, class_id, class_id, *query_terms, *(material_ids or []), limit),
    ).fetchall()
    return [_hit(row, row["rank_score"]) for row in rows]


def vector_search(question, class_id, limit=100, material_ids=None):
    if material_ids == []:
        return []
    vector = embed_texts([question])[0]
    points = (get_store().query(vector, class_id, limit) if material_ids is None
              else get_store().query(vector, class_id, limit, material_ids=material_ids))
    result = []
    for point in points:
        payload = point.get("payload") or {}
        if payload.get("class_id") != class_id or payload.get("chunk_id") != point.get("id"):
            continue
        if float(point.get("score", 0)) < 0.35:
            continue
        row = get_db().execute(
            """SELECT c.*,m.title FROM knowledge_chunks c JOIN materials m ON m.id=c.material_id
               WHERE c.id=? AND c.class_id=? AND c.index_status='ready'
                 AND m.class_id=? AND m.id=?""",
            (point["id"], class_id, class_id, payload.get("material_id")),
        ).fetchone()
        if row is not None and (material_ids is None or row["material_id"] in material_ids):
            result.append(_hit(row, point["score"]))
    return result


def search(question, class_id, mode="hybrid", limit=10, offset=0, material_ids=None):
    if mode == "keyword":
        hits = keyword_search(question, class_id, material_ids=material_ids)
    elif mode == "vector":
        hits = vector_search(question, class_id, material_ids=material_ids)
    else:
        keyword = keyword_search(question, class_id, material_ids=material_ids)
        vector = vector_search(question, class_id, material_ids=material_ids)
        candidates = {}
        for ranking in (keyword, vector):
            for rank, hit in enumerate(ranking, 1):
                item = candidates.setdefault(hit["chunk_id"], [hit, 0.0])
                item[1] += 1 / (60 + rank)
        hits = []
        for hit, score in sorted(candidates.values(), key=lambda item: (-item[1], item[0]["chunk_id"])):
            hits.append({**hit, "score": round(score, 6)})
    return {"hits": hits[offset : offset + limit], "total": len(hits)}
