import subprocess
import sys

from scripts.benchmark_http import is_success_status, validate_url


def test_benchmark_accepts_only_loopback_health_without_credentials():
    assert validate_url("http://127.0.0.1:18088/health") == "http://127.0.0.1:18088/health"
    for url in (
        "https://127.0.0.1/health",
        "http://example.com/health",
        "http://127.0.0.1/api/login",
        "http://user:password@127.0.0.1/health",
        "http://127.0.0.1/health?token=synthetic",
    ):
        try:
            validate_url(url)
        except ValueError:
            continue
        raise AssertionError(f"unsafe benchmark URL accepted: {url}")


def test_benchmark_treats_all_successful_2xx_statuses_as_success():
    assert is_success_status("200")
    assert is_success_status("202")
    assert is_success_status("204")
    assert not is_success_status("302")
    assert not is_success_status("500")
    assert not is_success_status("ERROR:TimeoutError")


def test_secret_gate_real_nonzero_then_clean_passes(tmp_path):
    repo = tmp_path / "synthetic-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
    scanner = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts" / "check_security.py"
    sample = repo / "synthetic.txt"
    synthetic_key = "AKIA" + ("0" * 16)
    sample.write_text(f"sample = {synthetic_key!r}\n", encoding="utf-8")
    failed = subprocess.run(
        [sys.executable, str(scanner), "--root", str(repo)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert failed.returncode != 0, failed.stdout + failed.stderr
    assert "aws-access-key-id" in failed.stdout

    sample.write_text("API_KEY = \"placeholder\"\n", encoding="utf-8")
    passed = subprocess.run(
        [sys.executable, str(scanner), "--root", str(repo)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert passed.returncode == 0, passed.stdout + passed.stderr
