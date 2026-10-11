#!/usr/bin/env python3
"""Synchronize classroom submission attachments and maintain their sole index."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path, PurePosixPath


MANIFEST = Path("docs/classroom/submission-manifest.json")
INDEX = Path("docs/classroom/提交材料/README.md")
SUBMISSION_ROOT = Path("docs/classroom/提交材料")


class SubmissionError(Exception):
    """A preflight or synchronization error that is safe to report to a user."""


def load_manifest(root: Path) -> list[dict]:
    try:
        data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubmissionError(f"cannot read manifest: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("entries"), list):
        raise SubmissionError("unsupported or malformed manifest")
    return data["entries"]


def safe_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (path.is_absolute() or "\\" in relative or ":" in relative or "\x00" in relative
            or not path.parts or any(part in ("", ".", "..") for part in path.parts)):
        raise SubmissionError(f"unsafe relative path: {relative!r}")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise SubmissionError(f"symlink path is not allowed: {relative}")
    try:
        current.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise SubmissionError(f"path escapes repository root: {relative}") from exc
    return current


def validate_entries(root: Path, entries: list[dict]) -> tuple[list[tuple[Path, Path, dict]], set[Path]]:
    copies: list[tuple[Path, Path, dict]] = []
    index = safe_path(root, INDEX.as_posix())
    if index.exists() and not index.is_file():
        raise SubmissionError("index must be a regular file")
    expected: set[Path] = {index}
    targets: set[Path] = set()
    for entry in entries:
        if (not isinstance(entry, dict) or entry.get("date") not in ("0923", "0930")
                or not isinstance(entry.get("title"), str) or not isinstance(entry.get("order"), str)
                or not isinstance(entry.get("files"), list) or not entry["files"]):
            raise SubmissionError("malformed submission entry")
        for item in entry.get("files", []):
            if not isinstance(item, dict):
                raise SubmissionError("malformed file entry")
            source_rel, target_rel = item.get("source"), item.get("target")
            if not isinstance(source_rel, str) or not isinstance(target_rel, str):
                raise SubmissionError("every file needs string source and target paths")
            source = safe_path(root, source_rel)
            target = safe_path(root, target_rel)
            if target.parent != root / SUBMISSION_ROOT / entry["date"]:
                raise SubmissionError(f"target must belong to submission date directory: {target_rel}")
            if target.exists() and not target.is_file():
                raise SubmissionError(f"target must be a regular file: {target_rel}")
            if target in targets:
                raise SubmissionError(f"duplicate target: {target_rel}")
            targets.add(target)
            expected.add(target)
            if item.get("canonical"):
                if source != target or item.get("kind") != "txt":
                    raise SubmissionError(f"canonical text must reference itself: {target_rel}")
            else:
                if not source.is_file():
                    raise SubmissionError(f"missing source file: {source_rel}")
                if source == target:
                    raise SubmissionError(f"copy source and target are identical: {source_rel}")
                copies.append((source, target, item))
    # Canonical text is user-authored submission content and must already exist.
    for _, target, item in [(safe_path(root, f["source"]), safe_path(root, f["target"]), f)
                            for e in entries for f in e.get("files", []) if f.get("canonical")]:
        if not target.is_file():
            raise SubmissionError(f"missing canonical text: {item['target']}")

    known_dirs = {root / SUBMISSION_ROOT, root / SUBMISSION_ROOT / "0923", root / SUBMISSION_ROOT / "0930"}
    for directory in known_dirs:
        if directory.exists():
            if directory.is_symlink() or not directory.is_dir():
                raise SubmissionError(f"invalid submission directory: {directory.relative_to(root)}")
            for child in directory.iterdir():
                if child.is_symlink():
                    raise SubmissionError(f"symlink in submission directory: {child.relative_to(root)}")
                if child.name == ".DS_Store" and child.is_file():
                    continue  # Finder metadata is not submission content.
                if child.is_file() and child not in expected:
                    raise SubmissionError(f"unknown extra file: {child.relative_to(root)}")
                if child.is_dir() and child not in known_dirs:
                    raise SubmissionError(f"unknown extra directory: {child.relative_to(root)}")
    return copies, expected


def render_index(entries: list[dict]) -> str:
    lines = ["# 课堂派提交材料", "", "提交时按日期打开对应目录；文字作业复制同名 `.txt` 全文，截图和 PDF 按链接上传。", ""]
    for date in ("0930", "0923"):
        lines.extend((f"## {date}", "", "| 顺序 | 作业 | 提交材料 |", "| --- | --- | --- |"))
        for entry in entries:
            if entry["date"] != date:
                continue
            links = []
            for item in entry["files"]:
                rel = PurePosixPath(item["target"])
                link = "/".join(rel.parts[-2:])
                suffix = rel.name.rsplit("-", 1)[-1].rsplit(".", 1)[0]
                label = {"txt": "文字答案", "pdf": "方案 PDF"}.get(item["kind"],
                        suffix if len(entry["files"]) > 2 or entry["order"] == "02" and date == "0930" else "截图")
                links.append(f"[{label}](<{link}>)")
            lines.append(f"| {entry['order']} | {entry['title']} | {'<br>'.join(links)} |")
        lines.append("")
    lines.extend(("## 同步", "", "在仓库根目录运行 `python3 scripts/prepare_classroom_submission.py` 同步附件并生成本索引。五份文字答案直接编辑同名 TXT，脚本保留其内容。", "", "运行 `python3 scripts/prepare_classroom_submission.py --check` 检查附件、额外文件和索引是否最新。", ""))
    return "\n".join(lines)


def check(root: Path, entries: list[dict], copies: list[tuple[Path, Path, dict]], expected: set[Path]) -> list[str]:
    problems = []
    for source, target, _ in copies:
        if not target.is_file():
            problems.append(f"missing copy: {target.relative_to(root)}")
        elif source.read_bytes() != target.read_bytes():
            problems.append(f"copy differs from source: {target.relative_to(root)}")
    index = root / INDEX
    wanted = render_index(entries)
    if not index.is_file() or index.read_text(encoding="utf-8") != wanted:
        problems.append(f"index is missing or stale: {INDEX}")
    return problems


def synchronize(root: Path, entries: list[dict], copies: list[tuple[Path, Path, dict]]) -> None:
    # Read every input and prepare all outputs before touching destination files.
    outputs = [(target, source.read_bytes()) for source, target, _ in copies]
    outputs.append((root / INDEX, render_index(entries).encode("utf-8")))
    for target, _ in outputs:
        target.parent.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        for target, content in outputs:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".submission-", delete=False) as stream:
                stream.write(content)
                staged.append((Path(stream.name), target))
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="repository root (primarily for isolated use)")
    parser.add_argument("--check", action="store_true", help="check copies and index without writing")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        entries = load_manifest(root)
        copies, expected = validate_entries(root, entries)
        if args.check:
            problems = check(root, entries, copies, expected)
            if problems:
                print("\n".join(problems), file=sys.stderr)
                return 1
            print("classroom submission files and index are up to date")
            return 0
        synchronize(root, entries, copies)
        print("classroom submission files and index synchronized")
        return 0
    except (OSError, SubmissionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
