"""Reproducible AI-free smoke test for Step8's three safety guardrails
(scripts/server/, plan/main/08-safety-guardrails.md): URL allowlist, max
concurrent sessions, idle-session timeout.

Same shape as scripts/temp/test_server.py: starts the custom-pages nginx
(:8080) and the session server (:8000) itself if they aren't already
running (only stops the ones it started), and drives everything over plain
HTTP -- no OpenAI API key or billed call involved.

Unlike test_server.py, this script needs the session server started with
small guardrail overrides (MAX_CONCURRENT_SESSIONS=2,
IDLE_SESSION_TIMEOUT_SECONDS=3, ALLOWED_DOMAINS=localhost) to exercise all
four checks in a few seconds, so it always launches its own server
subprocess with those env vars set (even if a server is already running on
:8000, in which case it's left alone and this script fails loudly instead
of silently testing against the wrong config).

Checks:
  1. max_sessions: create sessions up to the cap, then one more -> 429.
  2. URL allowlist via target_url: POST /sessions with a disallowed host -> 400.
  3. URL allowlist via /command: POST /sessions with the allowed host, then
     POST /sessions/{id}/command goto a disallowed host -> 400.
  4. idle timeout: create a session, touch nothing, wait past
     idle_timeout_seconds + the sweep interval, then GET .../snapshot -> 404.

Does not cover the AI-driven path (/run, /sessions/resume causing a
disallowed navigation via a click) -- that requires a real, billed OpenAI
API call and is out of scope for this script (see vertical-slice-ai-test
skill; run only with explicit user confirmation).

Run with:

    uv run python scripts/temp/test_server_safety_guardrails.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGES_HOST = "127.0.0.1"
PAGES_PORT = 8080
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
SERVER_BASE = f"http://{SERVER_HOST}:{SERVER_PORT}"
ALLOWED_URL = f"http://localhost:{PAGES_PORT}/index.html"
DISALLOWED_URL = "https://example.com/"

MAX_SESSIONS = 2
IDLE_TIMEOUT_SECONDS = 3
# Mirrors session_manager._SWEEP_INTERVAL_SECONDS; kept independent here (this
# script only needs an upper bound on how long to wait, not the exact value).
SWEEP_INTERVAL_SECONDS = 5


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(host, port):
            return
        time.sleep(0.3)
    raise RuntimeError(f"timed out waiting for {host}:{port}")


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{SERVER_BASE}{path}", data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else {})


def _create_session(target_url: str = ALLOWED_URL) -> tuple[int, dict]:
    return _request("POST", "/sessions", {"target_url": target_url})


def check_max_sessions() -> None:
    print(f"[1/4] max_sessions={MAX_SESSIONS}: filling up to the cap ...")
    session_ids = []
    try:
        for i in range(MAX_SESSIONS):
            status, body = _create_session()
            assert status == 201, f"expected 201 for session {i}, got {status}: {body}"
            session_ids.append(body["session_id"])
            print(f"  created session {i}: {body['session_id']}")

        print("  requesting one more session past the cap ...")
        status, body = _create_session()
        assert status == 429, f"expected 429 once max_sessions is reached, got {status}: {body}"
        print(f"  got 429 as expected: {body.get('detail')}")
    finally:
        for session_id in session_ids:
            _request("DELETE", f"/sessions/{session_id}")
    print("  PASS: max_sessions")


def check_allowlist_target_url() -> None:
    print("[2/4] URL allowlist via target_url: POST /sessions with a disallowed host ...")
    status, body = _create_session(target_url=DISALLOWED_URL)
    assert status == 400, f"expected 400 for a disallowed target_url, got {status}: {body}"
    print(f"  got 400 as expected: {body.get('detail')}")
    print("  PASS: allowlist (target_url)")


def check_allowlist_command() -> None:
    print("[3/4] URL allowlist via /command: allowed session, then goto a disallowed host ...")
    status, body = _create_session()
    assert status == 201, f"expected 201 for the allowed target_url, got {status}: {body}"
    session_id = body["session_id"]
    try:
        status, body = _request(
            "POST",
            f"/sessions/{session_id}/command",
            {"command": "goto", "args": [DISALLOWED_URL]},
        )
        assert status == 400, f"expected 400 for a disallowed goto via /command, got {status}: {body}"
        print(f"  got 400 as expected: {body.get('detail')}")
    finally:
        _request("DELETE", f"/sessions/{session_id}")
    print("  PASS: allowlist (/command)")


def check_idle_timeout() -> None:
    print(
        f"[4/4] idle timeout={IDLE_TIMEOUT_SECONDS}s: creating a session, "
        "then leaving it untouched ..."
    )
    status, body = _create_session()
    assert status == 201, f"expected 201, got {status}: {body}"
    session_id = body["session_id"]

    wait_seconds = IDLE_TIMEOUT_SECONDS + SWEEP_INTERVAL_SECONDS + 2
    print(f"  waiting {wait_seconds}s for the idle sweep to close it ...")
    time.sleep(wait_seconds)

    status, body = _request("GET", f"/sessions/{session_id}/snapshot")
    assert status == 404, f"expected 404 once the idle sweep has closed the session, got {status}: {body}"
    print(f"  got 404 as expected: {body.get('detail')}")
    print("  PASS: idle timeout")


def _run_scenario() -> None:
    check_max_sessions()
    check_allowlist_target_url()
    check_allowlist_command()
    check_idle_timeout()
    print("PASS (all 4 guardrail checks)")


def main() -> None:
    started_pages = None
    started_server = None

    if not _port_open(PAGES_HOST, PAGES_PORT):
        print(f"starting custom pages server on :{PAGES_PORT} ...")
        started_pages = subprocess.Popen(
            ["bash", "resources/custom_pages/serve.sh"],
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_port(PAGES_HOST, PAGES_PORT)
    else:
        print(f"custom pages server already running on :{PAGES_PORT}")

    if _port_open(SERVER_HOST, SERVER_PORT):
        raise RuntimeError(
            f"a session server is already running on :{SERVER_PORT}; this script always "
            "launches its own with small guardrail overrides, so stop the existing one first"
        )

    print(f"starting session server on :{SERVER_PORT} with guardrail overrides ...")
    env = {
        **os.environ,
        "MAX_CONCURRENT_SESSIONS": str(MAX_SESSIONS),
        "IDLE_SESSION_TIMEOUT_SECONDS": str(IDLE_TIMEOUT_SECONDS),
        "ALLOWED_DOMAINS": "localhost",
    }
    started_server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.server.main",
            "--host",
            SERVER_HOST,
            "--port",
            str(SERVER_PORT),
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port(SERVER_HOST, SERVER_PORT)

    try:
        _run_scenario()
    finally:
        if started_server is not None:
            started_server.terminate()
            started_server.wait(timeout=5)
        if started_pages is not None:
            started_pages.terminate()
            started_pages.wait(timeout=5)


if __name__ == "__main__":
    main()
