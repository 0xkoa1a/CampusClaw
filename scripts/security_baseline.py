#!/usr/bin/env python3
"""Read-only high-confidence secret-pattern scan of Git source files."""

from __future__ import annotations

import argparse
import subprocess
import re
import sys
from pathlib import Path


SOURCE_SUFFIXES = {
    ".c", ".cc", ".cjs", ".cpp", ".cs", ".css", ".go", ".h", ".hpp",
    ".htm", ".html", ".ini", ".java", ".js", ".json", ".jsx", ".kt",
    ".kts", ".md", ".mjs", ".php", ".ps1", ".py", ".pyw", ".rb", ".rs",
    ".sh", ".sql", ".svg", ".swift", ".toml", ".ts", ".tsx", ".txt",
    ".vue", ".xml", ".yaml", ".yml", ".zsh",
}
SOURCE_NAMES = {"agents", "makefile", "readme"}
EXCLUDED_PARTS = {
    ".git", ".venv", "venv", "vendor", "vendors", "node_modules", "dist",
    "build", "__pycache__", "coverage",
}
PATTERNS = (
    ("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe-live-secret", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
    ("stripe-webhook-secret", re.compile(r"\bwhsec_[A-Za-z0-9]{32,}\b")),
    ("openai-project-key", re.compile(r"\bsk-proj-[A-Za-z0-9_-]{30,}\b")),
    ("openai-secret-key", re.compile(r"\bsk-[A-Za-z0-9]{48,}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
)


def git_paths(root: Path) -> list[Path]:
    paths: set[Path] = set()
    for args in (
        ["git", "ls-files", "--cached", "-z"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ):
        completed = subprocess.run(args, cwd=root, check=True, stdout=subprocess.PIPE)
        for raw in completed.stdout.split(b"\0"):
            if raw:
                paths.add(Path(raw.decode("utf-8", errors="surrogateescape")))
    return sorted(paths, key=lambda item: item.as_posix())


def eligible(path: Path, *, history: bool = False) -> bool:
    if path.suffix.lower() not in SOURCE_SUFFIXES and path.name.lower() not in SOURCE_NAMES:
        return False
    if not history and path.name.lower().startswith(".env"):
        return False
    if any(part.lower() in EXCLUDED_PARTS for part in path.parts):
        return False
    return True


def scan(root: Path) -> list[tuple[str, int, str]]:
    findings = []
    for relative in git_paths(root):
        if not eligible(relative):
            continue
        path = root / relative
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            # Missing and non-text (including binary) files are outside this scan.
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            for category, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append((relative.as_posix(), line_number, category))
    return findings


def history_objects(root: Path) -> list[tuple[str, str]]:
    """Return unique reachable source blob IDs and their first Git path."""
    objects = subprocess.run(
        ["git", "rev-list", "--objects", "--all"], cwd=root, check=True,
        stdout=subprocess.PIPE,
    ).stdout.decode("utf-8", errors="surrogateescape")
    blob_paths: dict[str, str] = {}
    for record in objects.splitlines():
        object_id, separator, path = record.partition(" ")
        if separator and (eligible(Path(path), history=True) or Path(path).name.lower().startswith(".env")):
            blob_paths.setdefault(object_id, path)

    candidates = list(blob_paths.items())
    blobs = []
    for offset in range(0, len(candidates), 5000):
        batch = candidates[offset:offset + 5000]
        checked = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
            cwd=root, input="".join(f"{oid}\n" for oid, _ in batch).encode(),
            stdout=subprocess.PIPE, check=True,
        ).stdout.decode("ascii", errors="replace").splitlines()
        for (object_id, path), metadata in zip(batch, checked):
            fields = metadata.split()
            if len(fields) == 3 and fields[1] == "blob":
                try:
                    size = int(fields[2])
                except ValueError:
                    continue
                if size < 2 * 1024 * 1024:
                    blobs.append((object_id, path))
    return blobs


def scan_history(root: Path) -> list[tuple[str, str, int, str]]:
    """Scan unique, small, text source blobs reachable from local Git refs."""
    findings = []
    blobs = history_objects(root)
    for offset in range(0, len(blobs), 100):
        batch = blobs[offset:offset + 100]
        payload = subprocess.run(
            ["git", "cat-file", "--batch"], cwd=root, check=True,
            input="".join(f"{oid}\n" for oid, _ in batch).encode(),
            stdout=subprocess.PIPE,
        ).stdout
        cursor = 0
        for expected_oid, path in batch:
            header_end = payload.find(b"\n", cursor)
            if header_end < 0:
                break
            header = payload[cursor:header_end].split()
            cursor = header_end + 1
            if len(header) != 3 or header[1] != b"blob":
                continue
            try:
                size = int(header[2])
            except ValueError:
                continue
            body = payload[cursor:cursor + size]
            cursor += size + 1  # cat-file adds one delimiter newline after each blob.
            if size >= 2 * 1024 * 1024 or b"\0" in body:
                continue
            try:
                text = body.decode("utf-8")
            except UnicodeError:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                for category, pattern in PATTERNS:
                    if pattern.search(line):
                        findings.append((expected_oid, path, line_number, category))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--history", action="store_true", help="scan unique reachable Git source blobs")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        findings = scan_history(root) if args.history else scan(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"security baseline scan failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if args.history:
        for object_id, path, line_number, category in findings:
            print(f"{object_id}:{path}:{line_number}:{category}")
    else:
        for path, line_number, category in findings:
            print(f"{path}:{line_number}:{category}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
