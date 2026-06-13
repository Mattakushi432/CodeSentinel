#!/usr/bin/env python3
"""
CodeSentinel smoke test — validates a running deployment via HTTP.

Usage:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --base-url http://localhost:8000
    python scripts/smoke_test.py --base-url https://review.example.com

Exit code 0 if all tests pass, 1 if any fail.
No third-party dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Runner:
    base_url: str
    results: list[TestResult] = field(default_factory=list)

    def run(self, name: str, fn: Callable[[], tuple[bool, str]]) -> None:
        try:
            passed, detail = fn()
        except Exception as exc:
            passed, detail = False, f"Exception: {exc}"
        self.results.append(TestResult(name=name, passed=passed, detail=detail))
        status = "PASS" if passed else "FAIL"
        line = f"  [{status}] {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    def summary(self) -> bool:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        print()
        print(f"Results: {passed}/{total} passed", end="")
        if failed:
            print(f", {failed} FAILED")
        else:
            print()
        return failed == 0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, timeout: int = 10) -> tuple[int, bytes]:
    """Return (status_code, body_bytes). Raises on network errors."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _post(url: str, timeout: int = 10) -> tuple[int, bytes]:
    """POST with empty body. Returns (status_code, body_bytes)."""
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_health(base_url: str) -> tuple[bool, str]:
    """GET /health -> 200, body contains 'status' and 'ok'."""
    status, body = _get(f"{base_url}/health")
    if status != 200:
        return False, f"HTTP {status}"
    text = body.decode(errors="replace")
    if '"status"' not in text or '"ok"' not in text:
        return False, f"unexpected body: {text[:200]}"
    return True, f'HTTP {status}, body: {text.strip()}'


def test_metrics(base_url: str) -> tuple[bool, str]:
    """GET /metrics -> 200, body contains 'codesentinel_'."""
    status, body = _get(f"{base_url}/metrics")
    if status != 200:
        return False, f"HTTP {status}"
    text = body.decode(errors="replace")
    if "codesentinel_" not in text:
        return False, "response does not contain 'codesentinel_' metrics"
    # Count how many distinct codesentinel_ metric names we see
    names = {
        line.split("{")[0].split(" ")[0]
        for line in text.splitlines()
        if line.startswith("codesentinel_") and not line.startswith("codesentinel_#")
    }
    return True, f"HTTP {status}, {len(names)} codesentinel_ metric(s) found"


def test_login_page(base_url: str) -> tuple[bool, str]:
    """GET /auth/login -> 200, HTML contains 'CodeSentinel'."""
    status, body = _get(f"{base_url}/auth/login")
    if status != 200:
        return False, f"HTTP {status}"
    text = body.decode(errors="replace")
    if "CodeSentinel" not in text:
        return False, "page does not contain 'CodeSentinel'"
    return True, f"HTTP {status}, page title found"


def test_api_docs(base_url: str) -> tuple[bool, str]:
    """GET /api/docs -> 200 (Swagger UI)."""
    status, body = _get(f"{base_url}/api/docs")
    if status != 200:
        return False, f"HTTP {status}"
    text = body.decode(errors="replace")
    # Swagger UI always loads swagger-ui bundle or openapi spec reference
    if "swagger" not in text.lower() and "openapi" not in text.lower():
        return False, "response does not look like Swagger UI"
    return True, f"HTTP {status}, Swagger UI served"


def test_unknown_webhook(base_url: str) -> tuple[bool, str]:
    """POST /webhooks/99999 -> 404 (repository not found)."""
    status, body = _get(f"{base_url}/webhooks/99999")
    # The endpoint is POST-only but a GET should still 404/405 on a missing repo;
    # issue a POST to match real webhook behaviour.
    status, body = _post(f"{base_url}/webhooks/99999")
    if status != 404:
        return False, f"expected 404, got HTTP {status}"
    text = body.decode(errors="replace")
    return True, f"HTTP {status}, body: {text[:120].strip()}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test a running CodeSentinel deployment."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the CodeSentinel instance (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"CodeSentinel smoke test — target: {base_url}")
    print()

    runner = Runner(base_url=base_url)
    runner.run("GET /health -> 200 {\"status\": \"ok\"}", lambda: test_health(base_url))
    runner.run("GET /metrics -> 200, contains codesentinel_*", lambda: test_metrics(base_url))
    runner.run("GET /auth/login -> 200, contains 'CodeSentinel'", lambda: test_login_page(base_url))
    runner.run("GET /api/docs -> 200 (Swagger UI)", lambda: test_api_docs(base_url))
    runner.run("POST /webhooks/99999 -> 404 (unknown repo)", lambda: test_unknown_webhook(base_url))

    all_passed = runner.summary()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
