"""Loopback-only screenshot environment with public test accounts and synthetic data.

Run with a NEW temporary data directory. Never point this at the production DB.
Model/gateway settings are inherited from the environment; no key is written here.
Without a configured gateway, AI requests report their real service error, not a fake answer.
"""

import argparse
import io
import secrets
from pathlib import Path

from app import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    directory = Path(args.data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "evidence.sqlite3"
    if database.exists():
        parser.error("Use a fresh directory; existing evidence database is not overwritten")
    app = create_app({
        "SECRET_KEY": secrets.token_hex(32),
        "DATABASE_PATH": str(database), "UPLOAD_DIR": str(directory / "uploads"),
        "QDRANT_COLLECTION": "campusclaw_evidence_" + secrets.token_hex(8),
        "SESSION_COOKIE_SECURE": False,
        "SEED_TEACHER_PASSWORD": "teacher-test-password",
        "SEED_STUDENT_A_PASSWORD": "student-a-test-password",
        "SEED_STUDENT_B_PASSWORD": "student-b-test-password",
    })
    client = app.test_client()
    client.post("/api/login", json={"username": "teacher_a", "password": "teacher-test-password"})
    body = "# A班合成科学材料\n\n磁铁能吸引铁制品，不能吸引木块。木块不是铁磁性材料。\n\n这是用于课程截图的合成材料，不含真实学生数据。\n"
    response = client.post("/api/materials", data={"file": (io.BytesIO(body.encode()), "A班-合成科学材料.md")})
    if response.status_code != 201:
        raise RuntimeError("Synthetic upload failed")
    client.post("/api/logout")
    print(f"Evidence environment: http://127.0.0.1:{args.port}; synthetic material {response.json['id']}; index {response.json['index_status']}", flush=True)
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
