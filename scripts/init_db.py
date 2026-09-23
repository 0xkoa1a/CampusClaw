"""Initialize a new database once using passwords from the environment."""

import os
from pathlib import Path

from app.db import initialize


def main():
    passwords = [
        os.environ.get(key)
        for key in (
            "SEED_TEACHER_PASSWORD",
            "SEED_STUDENT_A_PASSWORD",
            "SEED_STUDENT_B_PASSWORD",
        )
    ]
    if any(not password for password in passwords):
        raise SystemExit(
            "Set all three SEED_*_PASSWORD variables before initialization"
        )
    path = Path(os.environ.get("DATABASE_PATH", "data/campusclaw.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    initialize(path, passwords)
    print(f"Initialized {path}")


if __name__ == "__main__":
    main()
