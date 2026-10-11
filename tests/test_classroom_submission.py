import importlib.util
import json
import shutil
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/prepare_classroom_submission.py"
MANIFEST = REPO / "docs/classroom/submission-manifest.json"
SPEC = importlib.util.spec_from_file_location("prepare_classroom_submission", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def make_root(tmp_path, *, extra=False):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "docs/classroom").mkdir(parents=True)
    shutil.copyfile(MANIFEST, root / MODULE.MANIFEST)
    entries = MODULE.load_manifest(root)
    for entry in entries:
        for item in entry["files"]:
            source = root / item["source"]
            source.parent.mkdir(parents=True, exist_ok=True)
            if item.get("canonical"):
                source.write_text(f"canonical: {entry['order']}\n", encoding="utf-8")
            else:
                source.write_bytes(f"source:{entry['order']}:{source.name}".encode())
    if extra:
        extra_path = root / MODULE.SUBMISSION_ROOT / "0923/extra.bin"
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_bytes(b"unknown")
    return root


def run(root, check=False):
    args = ["--root", str(root)]
    if check:
        args.append("--check")
    return MODULE.main(args)


def test_sync_is_correct_idempotent_and_check_is_read_only(tmp_path):
    root = make_root(tmp_path)
    assert run(root) == 0
    entries = MODULE.load_manifest(root)
    copies, expected = MODULE.validate_entries(root, entries)
    assert len(copies) == 11
    assert len([p for p in expected if p.suffix == ".jpg"]) == 10
    assert len([p for p in expected if p.suffix == ".pdf"]) == 1
    assert len([p for p in expected if p.suffix == ".txt"]) == 5
    canonical_paths = [root / item["target"] for entry in entries for item in entry["files"]
                       if item.get("canonical")]
    canonical_before = {path: path.read_bytes() for path in canonical_paths}
    snapshots = {p: p.read_bytes() for p in expected if p.is_file()}
    assert run(root, check=True) == 0
    assert {p: p.read_bytes() for p in snapshots} == snapshots
    assert run(root) == 0
    assert {p: p.read_bytes() for p in snapshots} == snapshots
    assert {p: p.read_bytes() for p in canonical_before} == canonical_before


def test_check_reports_missing_source_without_writing(tmp_path):
    root = make_root(tmp_path)
    missing = root / "docs/evidence/classroom/0930/02-ai-answer.jpg"
    missing.unlink()
    assert run(root, check=True) == 2
    assert not (root / MODULE.INDEX).exists()


def test_check_reports_missing_or_changed_copy(tmp_path):
    root = make_root(tmp_path)
    assert run(root) == 0
    copy = root / "docs/classroom/提交材料/0930/03-0930-课堂任务-toekn方案实现登录认证.jpg"
    copy.write_bytes(b"changed")
    assert run(root, check=True) == 1
    copy.unlink()
    assert run(root, check=True) == 1


def test_check_reports_stale_index(tmp_path):
    root = make_root(tmp_path)
    assert run(root) == 0
    index = root / MODULE.INDEX
    before = index.read_bytes()
    index.write_text("stale\n", encoding="utf-8")
    assert run(root, check=True) == 1
    assert index.read_bytes() == b"stale\n"
    assert before != index.read_bytes()


@pytest.mark.parametrize("bad_path", ["../outside", "/tmp/outside", "docs/../secret"])
def test_preflight_rejects_unsafe_manifest_paths_without_changes(tmp_path, bad_path):
    root = make_root(tmp_path)
    manifest_path = root / MODULE.MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["entries"][0]["files"][0]["target"] = bad_path
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(MODULE.SubmissionError, match="unsafe relative path"):
        entries = MODULE.load_manifest(root)
        MODULE.validate_entries(root, entries)
    assert not (root / MODULE.INDEX).exists()


def test_preflight_rejects_symlinked_source_and_duplicate_target(tmp_path):
    root = make_root(tmp_path)
    source = root / "docs/evidence/classroom/0930/01-bearer-materials.jpg"
    original = source.read_bytes()
    source.unlink()
    source.symlink_to(root / "docs/evidence/classroom/0930/02-ai-answer.jpg")
    with pytest.raises(MODULE.SubmissionError, match="symlink"):
        MODULE.validate_entries(root, MODULE.load_manifest(root))
    source.unlink()
    source.write_bytes(original)

    manifest_path = root / MODULE.MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["entries"][0]["files"][0]["target"] = data["entries"][1]["files"][0]["target"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(MODULE.SubmissionError, match="duplicate target"):
        MODULE.validate_entries(root, MODULE.load_manifest(root))


def test_preflight_rejects_unknown_extra_file(tmp_path):
    root = make_root(tmp_path, extra=True)
    with pytest.raises(MODULE.SubmissionError, match="unknown extra file"):
        MODULE.validate_entries(root, MODULE.load_manifest(root))


def test_teacher_home_mapping_matches_assignment():
    entry = next(e for e in MODULE.load_manifest(REPO) if e["title"] == "0923-系统运行截图")
    assert entry["files"][0]["source"].endswith("01-teacher-home.jpg")


def test_finder_metadata_is_preserved_and_ignored(tmp_path):
    root = make_root(tmp_path)
    metadata = root / MODULE.SUBMISSION_ROOT / ".DS_Store"
    metadata.write_bytes(b"finder")
    assert run(root) == 0
    assert run(root, check=True) == 0
    assert metadata.read_bytes() == b"finder"


def test_preflight_rejects_symlinked_index(tmp_path):
    root = make_root(tmp_path)
    index = root / MODULE.INDEX
    index.symlink_to(root / "outside.md")
    assert run(root) == 2
    assert not (root / "outside.md").exists()


@pytest.mark.parametrize("target", ["README.md", "docs/classroom/提交材料/0923/wrong-date.jpg"])
def test_preflight_rejects_target_outside_assignment_date(tmp_path, target):
    root = make_root(tmp_path)
    manifest_path = root / MODULE.MANIFEST
    data = json.loads(manifest_path.read_text())
    data["entries"][0]["files"][0]["target"] = target
    manifest_path.write_text(json.dumps(data))
    assert run(root) == 2
    assert not (root / MODULE.INDEX).exists()
