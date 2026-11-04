import json
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
import re

import pytest

from scripts import collect_week08_evidence as collector
from scripts import verify_week08 as verifier


def test_base_url_accepts_only_loopback_without_url_credentials():
    assert verifier.validate_base_url("http://127.0.0.1:18088") == "http://127.0.0.1:18088"
    assert verifier.validate_base_url("http://[::1]:18088/") == "http://[::1]:18088"
    assert verifier.validate_base_url("http://localhost:18088") == "http://localhost:18088"

    for url in (
        "https://example.com",
        "http://127.0.0.1:18088/with-path",
        "http://user:password@127.0.0.1:18088",
    ):
        with pytest.raises(verifier.VerificationError):
            verifier.validate_base_url(url)


def test_prepare_refuses_existing_state_before_any_api_call(tmp_path):
    state = tmp_path / "state.json"
    state.write_text('{"existing": true}\n', encoding="utf-8")

    class NoCalls:
        def __getattr__(self, name):
            raise AssertionError("prepare should reject existing state before network calls")

    with pytest.raises(verifier.VerificationError, match="新的 state 路径"):
        verifier.prepare(NoCalls(), SimpleNamespace(state=state, output=tmp_path / "out.json"))
    assert json.loads(state.read_text(encoding="utf-8")) == {"existing": True}


def test_check_pending_rejects_running_tasks():
    class RunningTaskApi:
        @staticmethod
        def json(method, path, *, token=None, **kwargs):
            return {"task": {"id": path.rsplit("/", 1)[-1], "status": "running"}}

    with pytest.raises(verifier.VerificationError, match="非 pending"):
        verifier.check_pending(RunningTaskApi(), ["synthetic-task"], "memory-only-token")


def test_api_http_error_does_not_expose_body_or_bearer_token(monkeypatch):
    api = verifier.Api("http://127.0.0.1:18088")
    body_marker = "private-response-body"
    bearer = "synthetic-bearer-secret"

    class ErrorOpener:
        @staticmethod
        def open(request, timeout):
            raise HTTPError(request.full_url, 403, "Forbidden", {}, BytesIO(body_marker.encode()))

    monkeypatch.setattr(api, "opener", ErrorOpener())
    with pytest.raises(verifier.VerificationError) as caught:
        api.json("GET", "/api/tasks/example", token=bearer)
    assert body_marker not in str(caught.value)
    assert bearer not in str(caught.value)


def test_real_script_cli_rejects_external_base_before_network(tmp_path):
    script = Path(verifier.__file__).resolve()
    output = tmp_path / "result.json"
    completed = subprocess.run(
        [sys.executable, str(script), "--base-url", "https://example.invalid",
         "--state", str(tmp_path / "state.json"), "--output", str(output), "verify"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 1
    assert "loopback" in completed.stdout
    assert "example.invalid" not in completed.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "failed"


def test_state_file_is_created_with_private_permissions(tmp_path):
    state_path = tmp_path / "state.json"
    verifier.save_state(state_path, {"assignment_id": 12, "task_ids": ["synthetic"]})

    assert os.stat(state_path).st_mode & 0o777 == 0o600
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert "token" not in state and "password" not in state


def test_collector_worker_events_parses_prefixed_json_and_keeps_original_fields():
    content = ('worker-1 | {"timestamp":1.25,"level":"INFO","event":"grading",'
               '"task_id":"task-a","class_id":2,"user_id":3,"attempt":2,'
               '"status":"succeeded","duration_ms":41,"extra":"discard"}')

    events, redacted = collector.worker_events(content, [], [])

    assert redacted == 0
    assert events == [{"timestamp": 1.25, "level": "INFO", "event": "grading",
                       "task_id": "task-a", "class_id": 2, "user_id": 3,
                       "attempt": 2, "status": "succeeded", "duration_ms": 41}]


def test_collector_worker_events_drops_event_containing_env_secret():
    secret = "synthetic-private-token"
    content = ('worker-1 | {"timestamp":1,"level":"INFO","event":"grading",'
               f'"task_id":"{secret}","status":"succeeded"}}')

    events, redacted = collector.worker_events(content, {secret}, [])

    assert events == []
    assert redacted == 1
    assert secret not in json.dumps(events)


def test_collector_scan_log_returns_only_service_category_counts():
    secret = "synthetic-private-secret"
    marker = 'AKIA' + '1' * 16
    patterns = [("aws-access-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"))]
    content = f"{secret} {secret} {marker}"

    findings = collector.scan_log("worker", content, {secret}, patterns)

    assert findings == [
        {"service": "worker", "category": "aws-access-key-id", "count": 1},
        {"service": "worker", "category": "env-secret", "count": 2},
    ]
    serialized = json.dumps(findings)
    assert secret not in serialized and marker not in serialized
