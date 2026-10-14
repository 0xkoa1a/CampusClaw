"""CLab-side recoverable snapshot of the explicitly named Compose deployment."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import uuid


def docker(*arguments):
    return subprocess.check_output(["sudo", "-n", "docker", *arguments], text=True).strip()


def table_signatures(database, selected=None):
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        result = {}
        for table in selected or ("users", "classes", "materials", "knowledge_entries", "knowledge_chunks", "chunk_terms"):
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            if not columns:
                continue
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            serialized = sorted(json.dumps(row, ensure_ascii=False) for row in rows)
            result[table] = {"rows": len(rows), "sha256": hashlib.sha256('\n'.join(serialized).encode()).hexdigest()}
        return result
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deployment-dir", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--container", default="campusclaw-yyx-app-1")
    args = parser.parse_args()
    source, backup = args.deployment_dir.resolve(), args.backup_dir.resolve()
    if not (source / "docker-compose.yml").is_file() or not (source / ".env").is_file():
        parser.error("explicit deployment directory must contain Compose and private .env")
    if backup.exists() or backup == source or source in backup.parents:
        parser.error("use a fresh backup directory outside the deployment")
    backup.mkdir(parents=True, mode=0o700)
    image = docker("inspect", "--format", "{{.Image}}", args.container)
    docker("image", "tag", image, "campusclaw-yyx-app:before-week05-20261014")
    private_env = backup / ".env"
    shutil.copyfile(source / ".env", private_env)
    private_env.chmod(0o600)
    archive = backup / "source.tar.gz"
    subprocess.run(["tar", "--exclude=.env", "--exclude=data", "--exclude=uploads", "--exclude=.git", "-czf", str(archive), "-C", str(source), "."], check=True)
    archive.chmod(0o600)
    temporary = "/tmp/week05-backup-" + uuid.uuid4().hex + ".sqlite3"
    docker("exec", args.container, "python", "-c",
           "import sqlite3; source=sqlite3.connect('/app/data/campusclaw.sqlite3'); target=sqlite3.connect(" + repr(temporary) + "); source.backup(target); target.close(); source.close()")
    docker("cp", args.container + ":" + temporary, str(backup / "database.sqlite3"))
    docker("cp", args.container + ":/app/uploads", str(backup / "uploads"))
    subprocess.run(["sudo", "-n", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(backup)], check=True)
    (backup / "database.sqlite3").chmod(0o600)
    docker("exec", args.container, "python", "-c", "from pathlib import Path; Path(" + repr(temporary) + ").unlink()")
    uploads = {str(file.relative_to(backup / "uploads")): hashlib.sha256(file.read_bytes()).hexdigest() for file in (backup / "uploads").rglob("*") if file.is_file()}
    manifest = {"previous_image": image, "tables": table_signatures(backup / "database.sqlite3"), "uploads": uploads,
                "rollback_image": "campusclaw-yyx-app:before-week05-20261014"}
    (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({"backup_dir": str(backup), "previous_image": image,
                      "table_counts": {name: item["rows"] for name, item in manifest["tables"].items()}, "upload_files": len(uploads)}))


if __name__ == "__main__":
    main()
