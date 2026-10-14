import importlib.util
from pathlib import Path

import pytest


RUNNER_PATH = Path(__file__).parents[1] / "apitest" / "run_all.py"
SPEC = importlib.util.spec_from_file_location("apitest_run_all", RUNNER_PATH)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_case_loader_finds_run_functions_and_preserves_order():
    cases = runner.load_cases()
    assert [name for name, _ in cases] == list(runner.ORDER)
    assert all(callable(run) for _, run in cases)


@pytest.mark.parametrize("url", ["http://localhost", "http://localhost:8080", "http://127.0.0.1:1/"])
def test_loopback_base_url(url):
    assert runner.validate_base_url(url).startswith("http://")


@pytest.mark.parametrize("url", ["https://localhost", "http://example.com", "http://127.0.0.2:8080", "http://user@localhost", "http://localhost/api"])
def test_non_loopback_or_non_origin_base_url_is_rejected(url):
    with pytest.raises(ValueError):
        runner.validate_base_url(url)


def test_report_escapes_html_and_redacts_secrets_tokens_and_error_text():
    secret = "known-secret<"
    report = runner.render_report([{"case": "api/<x>", "passed": False,
                                   "detail": f"bad {secret} Bearer abc.def access_token=xyz <script>alert(1)</script>"}], [secret])
    assert "&lt;script&gt;" in report and "&lt;x&gt;" in report
    assert "known-secret" not in report and "abc.def" not in report and "xyz" not in report


def test_cli_rejects_configuration_without_starting_service(capsys):
    result = runner.main(["--base-url", "http://example.com", "--database-path", "/missing"])
    assert result == 2
    assert "configuration error" in capsys.readouterr().err
