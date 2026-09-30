"""Create a private demo .env without overwriting existing credentials."""

import argparse
import os
import secrets
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".env"))
    parser.add_argument("--python-image", default="python:3.12-slim")
    args = parser.parse_args()
    if any(char.isspace() for char in args.python_image):
        parser.error("image reference must not contain whitespace")
    values = {
        key: secrets.token_urlsafe(32)
        for key in (
            "SECRET_KEY",
            "SEED_TEACHER_PASSWORD",
            "SEED_STUDENT_A_PASSWORD",
            "SEED_STUDENT_B_PASSWORD",
        )
    }
    values.update(
        MAX_UPLOAD_BYTES="1048576", PYTHON_IMAGE=args.python_image,
        EMBEDDING_BASE_URL="https://ai-gateway.devops.hello1023.com/v1",
        EMBEDDING_API_KEY="", EMBEDDING_MODEL="course-embedding",
        EMBEDDING_DIM="2048", CHAT_MODEL="course-chat",
        QDRANT_IMAGE="ghcr.io/qdrant/qdrant/qdrant:v1.19.1",
    )
    try:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.exit(1, f"Refusing to overwrite {args.output}\n")
    with os.fdopen(fd, "w") as output:
        output.write("".join(f"{key}={value}\n" for key, value in values.items()))
    print(f"Created {args.output} (mode 0600); credentials are not printed.")


if __name__ == "__main__":
    main()
