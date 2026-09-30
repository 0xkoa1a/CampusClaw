"""Index existing third-lesson material after configuring the gateway."""

import argparse

from app import create_app
from app.db import get_db
from app.gateway import GatewayUnavailable
from app.indexing import index_material
from app.vector import VectorUnavailable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Rebuild already-ready material too")
    arguments = parser.parse_args()
    app = create_app()
    with app.app_context():
        rows = get_db().execute(
            "SELECT id,class_id FROM materials " + ("" if arguments.all else "WHERE index_status!='ready' ") + "ORDER BY id"
        ).fetchall()
        failed = 0
        for row in rows:
            try:
                count = index_material(row["id"], row["class_id"], replace=arguments.all)
                print(f"material {row['id']}: ready ({count} chunks)")
            except (GatewayUnavailable, VectorUnavailable, ValueError) as exc:
                failed += 1
                print(f"material {row['id']}: failed ({exc})")
        print(f"indexed={len(rows) - failed} failed={failed}")
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
