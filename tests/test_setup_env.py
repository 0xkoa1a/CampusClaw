import stat
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_env.py"


def test_private_credentials_and_no_overwrite(tmp_path):
    target = tmp_path / ".env"
    command = [sys.executable, str(SCRIPT), "--output", str(target)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    content = target.read_text()
    values = dict(line.split("=", 1) for line in content.splitlines())
    secrets = [values[key] for key in values if key == "SECRET_KEY" or key.endswith("PASSWORD")]
    assert len(set(secrets)) == 4
    assert all(len(value) >= 40 and value not in result.stdout for value in secrets)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode != 0
    assert target.read_text() == content


def test_image_override_and_reject_newline(tmp_path):
    target = tmp_path / ".env"
    image = "public.ecr.aws/docker/library/python:3.12-slim"
    command = [sys.executable, str(SCRIPT), "--output", str(target), "--python-image"]
    subprocess.run(command + [image], capture_output=True, check=True)
    assert f"PYTHON_IMAGE={image}\n" in target.read_text()
    invalid = subprocess.run(command + ["python\nINJECT=value"], capture_output=True)
    assert invalid.returncode != 0
