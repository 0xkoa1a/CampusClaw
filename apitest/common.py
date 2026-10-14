import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request


def request(context, method, path, *, token=None, payload=None, stream=False):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Accept": "text/event-stream" if stream else "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(context["base_url"] + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=context.get("timeout", 60)) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def json_body(result):
    status, _headers, body = result
    assert 200 <= status < 300, f"HTTP {status}: {body.decode('utf-8', 'replace')[:500]}"
    return json.loads(body.decode("utf-8"))


def _db_uri(context):
    return "file:" + urllib.parse.quote(context["database_path"], safe="/") + "?mode=ro"


def db_rows(context, table, where="1=1", params=()):
    connection = sqlite3.connect(_db_uri(context), uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table} WHERE {where}", params)]
    finally:
        connection.close()


def assert_db_value(context, table, key, value, **fields):
    rows = db_rows(context, table, f"{key}=?", (value,))
    assert len(rows) == 1, f"expected one {table} row for {key}={value}, got {len(rows)}"
    for field, expected in fields.items():
        assert rows[0][field] == expected, f"{table}.{field} mismatch"
    return rows[0]


def require_columns(context, table, required):
    con = sqlite3.connect(_db_uri(context), uri=True)
    try:
        columns = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()
    assert required <= columns, f"{table} missing expected columns: {sorted(required - columns)}"
