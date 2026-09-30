"""Qdrant point storage. Chunk text is deliberately kept out of payloads."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app


class VectorUnavailable(RuntimeError):
    pass


class QdrantStore:
    def __init__(self, base_url, collection, dimension):
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self.dimension = dimension

    def _request(self, method, path, payload=None, missing_ok=False):
        request = Request(
            self.base_url + path,
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=8) as response:
                return json.load(response)
        except HTTPError as exc:
            if missing_ok and exc.code == 404:
                return None
            raise VectorUnavailable("向量服务暂时不可用") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise VectorUnavailable("向量服务暂时不可用") from exc

    @property
    def path(self):
        return f"/collections/{self.collection}"

    def ensure_collection(self):
        response = self._request("GET", self.path, missing_ok=True)
        if response is None:
            self._request("PUT", self.path, {"vectors": {"size": self.dimension, "distance": "Cosine"}})
            return
        try:
            size = response["result"]["config"]["params"]["vectors"]["size"]
            if size != self.dimension:
                raise VectorUnavailable("向量库维度与课程网关不一致")
        except (KeyError, TypeError) as exc:
            raise VectorUnavailable("向量库配置格式不正确") from exc

    def upsert(self, points):
        self.ensure_collection()
        for begin in range(0, len(points), 32):
            self._request("PUT", self.path + "/points?wait=true", {"points": points[begin : begin + 32]})

    def delete(self, ids):
        if ids:
            self._request("POST", self.path + "/points/delete?wait=true", {"points": ids})

    def query(self, vector, class_id, limit):
        self.ensure_collection()
        response = self._request("POST", self.path + "/points/query", {
            "query": vector,
            "filter": {"must": [{"key": "class_id", "match": {"value": class_id}}]},
            "score_threshold": 0.35,
            "limit": limit,
            "with_payload": True,
        })
        try:
            return response["result"]["points"]
        except (KeyError, TypeError) as exc:
            raise VectorUnavailable("向量服务返回格式不正确") from exc


def get_store():
    return current_app.config.get("VECTOR_STORE") or QdrantStore(
        current_app.config["QDRANT_URL"],
        current_app.config["QDRANT_COLLECTION"],
        current_app.config["EMBEDDING_DIM"],
    )
