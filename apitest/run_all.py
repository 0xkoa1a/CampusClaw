#!/usr/bin/env python3
"""Run stdlib-only HTTP acceptance cases against a local CampusClaw instance."""
import argparse
import html
import importlib.util
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CASE_ROOT = Path(__file__).resolve().parent / "cases"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
ORDER = (
    "api/login/POST.py", "api/me/GET.py", "api/search/POST.py",
    "api/skills/POST.py", "api/skills/PUT.py", "api/skills/DELETE.py",
    "api/agents/POST.py", "api/agents/PUT.py",
    "api/conversations/POST.py", "api/conversations/GET.py",
    "api/conversations/id/messages/POST.py", "api/conversations/id/GET.py",
    "api/conversations/id/DELETE.py",
)
SECRET_NAMES = ("SEED_TEACHER_PASSWORD", "SEED_STUDENT_A_PASSWORD", "SEED_STUDENT_B_PASSWORD")


def validate_base_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("--base-url must be an http URL on localhost or 127.0.0.1")
    if parsed.path not in ("", "/"):
        raise ValueError("--base-url must not include a path")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ValueError("--base-url port is invalid")
    return f"http://{parsed.netloc}"


def load_cases(case_root=CASE_ROOT, order=ORDER):
    cases = []
    for relative in order:
        path = case_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"missing API case: {relative}")
        spec = importlib.util.spec_from_file_location("apitest_case_" + str(len(cases)), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not callable(getattr(module, "run", None)):
            raise TypeError(f"API case has no run(context): {relative}")
        cases.append((relative, module.run))
    return cases


def redact(value, secrets=()):
    text = str(value)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(access_token[\"'\s:=]+)[^\s,}\"']+", r"\1[REDACTED]", text)
    return text


def context_redactions(context):
    values = list(context["secrets"].values()) + list(context["tokens"].values())
    values.extend(context.get(key, "") for key in ("skill_source", "agent_role_prompt", "expected_message_content"))
    return values


def render_report(results, secrets=()):
    rows = []
    for item in results:
        status = "PASS" if item["passed"] else "ERROR"
        detail = redact(item["detail"], secrets)
        rows.append("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(item["case"]), status,
            html.escape(detail, quote=True)))
    passed = sum(bool(r["passed"]) for r in results)
    return """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>API 验收报告</title>
<h1>API 验收报告</h1><p>通过：{} / {}</p><table><thead><tr><th>Case</th><th>结果</th><th>详情</th></tr></thead><tbody>{}</tbody></table></html>
""".format(passed, len(results), "".join(rows))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="local HTTP origin, e.g. http://127.0.0.1:8080")
    parser.add_argument("--database-path", required=True, help="absolute SQLite path used by this same app instance")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        base_url = validate_base_url(args.base_url)
        db_path = Path(args.database_path)
        if not db_path.is_absolute() or not db_path.is_file():
            raise ValueError("--database-path must be an existing absolute SQLite file")
        secrets = {name: os.environ.get(name, "") for name in SECRET_NAMES}
        if any(not value for value in secrets.values()):
            raise ValueError("all three SEED_*_PASSWORD environment variables are required")
        context = {"base_url": base_url, "database_path": str(db_path.resolve()), "timeout": args.timeout,
                   "secrets": secrets, "tokens": {}, "identities": {}, "synthetic_prefix": "apitest-" + uuid.uuid4().hex[:12],
                   "skill_name": "apitest-skill-" + uuid.uuid4().hex[:10],
                   "agent_name": "apitest-agent-" + uuid.uuid4().hex[:10], "search_term": "入门"}
        cases = load_cases()
    except (ValueError, OSError, FileNotFoundError) as exc:
        print(redact(f"apitest configuration error: {exc}", (os.environ.get(n, "") for n in SECRET_NAMES)), file=sys.stderr)
        return 2

    results = []
    for name, run in cases:
        try:
            detail = run(context)
            results.append({"case": name, "passed": True, "detail": detail})
        except Exception as exc:  # Capture per-case diagnostics without leaking credentials or response bodies.
            results.append({"case": name, "passed": False,
                            "detail": redact(f"{type(exc).__name__}: {exc}", context_redactions(context))})
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "latest.html"
    report_path.write_text(render_report(results, secrets.values()), encoding="utf-8")
    for item in results:
        print(f"{'PASS' if item['passed'] else 'ERROR'} {item['case']}: {redact(item['detail'], context_redactions(context))}")
    print(f"HTML report: {report_path.relative_to(ROOT)}")
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
