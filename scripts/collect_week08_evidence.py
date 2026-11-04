"""Collect allowlisted metadata and redacted Week 8 runtime evidence on CLab."""

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


ROOT = Path("/home/ubuntu/workspace/campusclaw/verification/week08")
PROJECT = "campusclaw-week08-20261104"
LOG_SERVICES = ("app", "worker", "mcp-demo")
INSPECT_SERVICES = (*LOG_SERVICES, "rabbitmq")
FIELDS = ('timestamp', 'level', 'event', 'task_id', 'class_id', 'user_id', 'status', 'attempt', 'duration_ms')


def command(args, *, timeout=120):
    return subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout).stdout.strip()


def write_private(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(content)


def compose(*args):
    return ["docker", "compose", "--project-directory", str(ROOT), "-f", str(ROOT / "docker-compose.yml"),
            "-p", PROJECT, *args]

def env_secrets():
    secrets = set()
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, raw = line.partition("=")
        if sep and re.search(r"(?:KEY|PASSWORD|TOKEN|SECRET)", key, re.I):
            try:
                parts = shlex.split(raw, comments=True)
                value = parts[0] if parts else ""
            except ValueError:
                value = raw.strip().strip("\"'")
            if value:
                secrets.add(value)
    return secrets

def scanners():
    spec = importlib.util.spec_from_file_location("security_baseline", ROOT / "scripts/security_baseline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PATTERNS


def scan_log(service, content, secrets, patterns):
    findings = {}
    for secret in secrets:
        count = content.count(secret)
        if count:
            findings["env-secret"] = findings.get("env-secret", 0) + count
    for category, pattern in patterns:
        count = sum(1 for _ in pattern.finditer(content))
        if count:
            findings[category] = count
    return [{"service": service, "category": category, "count": count}
            for category, count in sorted(findings.items())]


def worker_events(content, secrets, patterns):
    events, redacted = [], 0
    for line in content.splitlines():
        try:
            record = json.loads(line[line.index('{'):])
        except (ValueError, TypeError):
            continue
        if not isinstance(record, dict) or record.get("event") != "grading":
            continue
        event = {key: record[key] for key in FIELDS
                 if key in record and isinstance(record[key], (str, int, float, bool, type(None)))}
        serialized = json.dumps(event, ensure_ascii=False)
        if any(secret in serialized for secret in secrets) or any(pattern.search(serialized) for _, pattern in patterns):
            redacted += 1
            continue
        events.append(event)
    return events, redacted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    stage = "preflight"
    try:
        if not ROOT.is_dir() or not (ROOT / ".env").is_file():
            raise RuntimeError
        args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(args.output_dir, 0o700)
        stage = "installed-packages"
        package_code = ("import importlib.metadata,json; print(json.dumps(sorted(["
                        "{'name':d.metadata.get('Name') or d.name,'version':d.version} "
                        "for d in importlib.metadata.distributions()],key=lambda x:x['name'].lower())))")
        packages = json.loads(command(compose("exec", "-T", "app", "python", "-c", package_code)))
        write_private(args.output_dir / "installed-requirements.txt",
                      "".join(f"{p['name']}=={p['version']}\n" for p in packages))
        stage = "inspect"
        template = ('{"Id":{{json .Id}},"Image":{{json .Image}},"Config.Image":{{json .Config.Image}},'
                    '"State.Status":{{json .State.Status}},"State.Health.Status":'
                    '{{with index .State "Health"}}{{json .Status}}{{else}}null{{end}},"Mounts.Name":['
                    '{{range $i,$m := .Mounts}}{{if $i}},{{end}}{{json $m.Name}}{{end}}]}')
        containers = {}
        for service in INSPECT_SERVICES:
            ids = command(compose("ps", "-q", service)).splitlines()
            records = [json.loads(command(["docker", "inspect", "--format", template, identifier])) for identifier in ids]
            containers[service] = records
        stage = "rabbit-version"
        rabbit_version = command(compose("exec", "-T", "rabbitmq", "rabbitmq-diagnostics", "server_version"))
        stage = "logs"
        secrets, patterns = env_secrets(), scanners()
        findings, events, redacted = [], [], 0
        for service in LOG_SERVICES:
            content = command(compose("logs", "--no-color", "--no-log-prefix", "--tail", "10000", service), timeout=180)
            findings.extend(scan_log(service, content, secrets, patterns))
            if service == "worker":
                events, redacted = worker_events(content, secrets, patterns)
        if redacted:
            findings.append({"service": "worker", "category": "redacted-grading-event", "count": redacted})
        metadata = {"collected_at": datetime.now(timezone.utc).isoformat(), "compose_project": PROJECT,
                    "containers": containers, "rabbitmq_server_version": rabbit_version,
                    "log_findings": findings}
        write_private(args.output_dir / "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
        write_private(args.output_dir / "worker-events.json", json.dumps(events, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"status": "collected", "services": list(LOG_SERVICES), "packages": len(packages),
                          "grading_events": len(events), "log_findings": len(findings)}, ensure_ascii=False))
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "stage": stage}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
