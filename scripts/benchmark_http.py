"""Loopback-only sampler for health and classroom HTTP endpoints."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_CONCURRENCY = 4
DEFAULT_REQUESTS = 20
DEFAULT_TIMEOUT = 2.0
ALLOWED_PATHS = (
    re.compile(r"^/health$"),
    re.compile(r"^/api/tasks$"),
    re.compile(r"^/api/tasks/[A-Za-z0-9_-]+$"),
    re.compile(r"^/api/search$"),
    re.compile(r"^/api/assignments/[0-9]+/submissions$"),
)


def validate_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise ValueError("URL must be plain HTTP on loopback without credentials")
    if not any(pattern.fullmatch(parsed.path) for pattern in ALLOWED_PATHS) or parsed.query or parsed.fragment:
        raise ValueError("path must be /health or an allowed classroom API; query strings are forbidden")
    host = (parsed.hostname or "").lower()
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        raise ValueError("host must be localhost or a loopback IP address")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("invalid port")
    return value.rstrip("/")


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def env_timeout() -> float:
    try:
        value = float(os.environ.get("CAMPUSCLAW_BENCHMARK_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError as exc:
        raise ValueError("CAMPUSCLAW_BENCHMARK_TIMEOUT must be numeric") from exc
    if not 0.1 <= value <= 60:
        raise ValueError("CAMPUSCLAW_BENCHMARK_TIMEOUT must be between 0.1 and 60 seconds")
    return value


def is_success_status(status: str) -> bool:
    return status.isdigit() and 200 <= int(status) < 300


def sample(
    url: str, method: str, body: bytes | None, token: str, request_number: int, timeout: float
) -> tuple[float, str]:
    started = time.perf_counter()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    if urlsplit(url).path.endswith("/submissions"):
        headers["Idempotency-Key"] = 'benchmark-' + uuid.uuid4().hex
    try:
        request = Request(url, data=body, headers=headers, method=method)
        with urlopen(request, timeout=timeout) as response:
            status = str(response.status)
            response.read()
    except HTTPError as exc:
        status = str(exc.code)
    except Exception as exc:  # Each failed request remains visible in the sample set.
        status = f"ERROR:{type(exc).__name__}"
    return time.perf_counter() - started, status


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Run parameters: CAMPUSCLAW_BENCHMARK_CONCURRENCY (1..64, default 4), "
            "CAMPUSCLAW_BENCHMARK_REQUESTS (1..1000, default 20), "
            "CAMPUSCLAW_BENCHMARK_TIMEOUT (0.1..60 seconds, default 2). "
            "API authorization comes only from CAMPUSCLAW_BENCHMARK_TOKEN; POST JSON comes from "
            "CAMPUSCLAW_BENCHMARK_JSON. Tokens and request bodies are not written to output."
        ),
    )
    parser.add_argument("url", help="loopback URL for /health, submit, query, or search")
    parser.add_argument("--method", choices=("GET", "POST"), help="defaults from the selected endpoint")
    parser.add_argument("--json-env", default="CAMPUSCLAW_BENCHMARK_JSON", help="environment variable containing POST JSON")
    parser.add_argument("--output", type=Path, help="raw JSON output path; otherwise a timestamped file is created")
    args = parser.parse_args()
    try:
        url = validate_url(args.url)
        concurrency = env_int("CAMPUSCLAW_BENCHMARK_CONCURRENCY", DEFAULT_CONCURRENCY, 1, 64)
        request_count = env_int("CAMPUSCLAW_BENCHMARK_REQUESTS", DEFAULT_REQUESTS, 1, 1000)
        timeout = env_timeout()
    except ValueError as exc:
        parser.error(str(exc))
    path = urlsplit(url).path
    is_post_route = path == "/api/search" or path.endswith("/submissions")
    method = args.method or ("POST" if is_post_route else "GET")
    if (method == "POST") != is_post_route:
        parser.error("POST is allowed only for submission and search routes; other routes use GET")
    body = None
    if method == "POST":
        if args.json_env not in os.environ:
            parser.error(f"POST requires JSON in environment variable {args.json_env}")
        try:
            body = json.dumps(json.loads(os.environ[args.json_env]), separators=(",", ":")).encode()
        except (json.JSONDecodeError, TypeError) as exc:
            parser.error(f"{args.json_env} must contain JSON ({type(exc).__name__})")
    token = "" if path == "/health" else os.environ.get("CAMPUSCLAW_BENCHMARK_TOKEN", "")
    if path != "/health" and not token:
        parser.error("API benchmarks require CAMPUSCLAW_BENCHMARK_TOKEN")

    started_at = datetime.now(timezone.utc).isoformat()
    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        samples = list(
            pool.map(
                lambda index: sample(url, method, body, token, index + 1, timeout),
                range(request_count),
            )
        )
    elapsed = time.perf_counter() - wall_started
    for index, (duration, status) in enumerate(samples, 1):
        print(f"request={index:04d} elapsed_seconds={duration:.6f} status={status}")
    durations = sorted(duration for duration, _ in samples)
    p95 = durations[max(0, math.ceil(0.95 * len(durations)) - 1)]
    failures = sum(not is_success_status(status) for _, status in samples)
    parameters = {
        "target": url,
        "method": method,
        "body_sha256": hashlib.sha256(body or b"").hexdigest(),
        "concurrency": concurrency,
        "requests": request_count,
        "timeout_seconds": timeout,
    }
    summary = {
        **parameters,
        "elapsed_seconds": elapsed,
        "p95_seconds": p95,
        "throughput_requests_per_second": request_count / elapsed,
        "failures": failures,
    }
    output = args.output or Path(f"benchmark-samples-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json")
    output.write_text(
        json.dumps(
            {
                "started_at_utc": started_at,
                "parameters": parameters,
                "summary": summary,
                "samples": [
                    {"request": index, "elapsed_seconds": duration, "status": status}
                    for index, (duration, status) in enumerate(samples, 1)
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"target={url} method={method} body_sha256={parameters['body_sha256']} "
        f"requests={request_count} concurrency={concurrency} timeout_seconds={timeout:g} "
        f"elapsed_seconds={elapsed:.6f} p95_seconds={p95:.6f} "
        f"throughput_requests_per_second={request_count / elapsed:.3f} failures={failures} samples_json={output}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
