"""Create a new synthetic Compose environment using gateway settings on CLab."""

import argparse
import os
from pathlib import Path
import secrets
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-env", type=Path, required=True)
    parser.add_argument("--project", default="campusclaw-week06-acceptance")
    parser.add_argument("--port", type=int, default=18086)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if (root / ".env").exists() or root == args.gateway_env.resolve().parent:
        raise RuntimeError("Use a fresh source copy, never the formal deployment directory")
    if not 1024 <= args.port <= 65535 or not args.project.startswith("campusclaw-week06-"):
        raise ValueError("Invalid isolated project or port")
    settings = {}
    for line in args.gateway_env.read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"EMBEDDING_BASE_URL", "EMBEDDING_API_KEY", "EMBEDDING_MODEL", "EMBEDDING_DIM", "CHAT_MODEL", "PYTHON_IMAGE", "QDRANT_IMAGE"}:
            settings[key] = value.strip().strip("\"'")
    if not settings.get("EMBEDDING_API_KEY"):
        raise RuntimeError("Gateway key is not configured")
    settings.update(SECRET_KEY=secrets.token_hex(32), MCP_AUTH_TOKEN=secrets.token_hex(32),
                    SEED_TEACHER_PASSWORD="teacher-test-password", SEED_STUDENT_A_PASSWORD="student-a-test-password",
                    SEED_STUDENT_B_PASSWORD="student-b-test-password", APP_PORT=str(args.port))
    fd = os.open(root / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write("".join(f"{key}={value}\n" for key, value in settings.items()))
    subprocess.run(["docker", "compose", "-p", args.project, "up", "--build", "-d", "--wait"], cwd=root, check=True)
    print("Synthetic acceptance environment started on loopback port", args.port)


if __name__ == "__main__":
    main()
