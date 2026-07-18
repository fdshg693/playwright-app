"""Real-AI smoke test for the Step3+Step4 path: POST /sessions/{id}/run.

Unlike scripts/temp/test_server.py (which only exercises the human-driven
/command + /snapshot endpoints for free), this drives the session server's
`/run` endpoint end-to-end against a real, billed AI API -- validating both
Step3 (server-side task orchestration, previously untested against a real
API) and Step4 (add_expectation / step-commented spec assembly) in one run.

Starts the custom-pages nginx (:8080) and the session server (:8000)
themselves if they aren't already running, and only stops the ones it
started.

Run with:

    uv run python scripts/temp/test_server_ai_run.py
"""

from __future__ import annotations

import json
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
TARGET_URL = f"http://localhost:{PAGES_PORT}/index.html"
STORY_PATH = "scripts/stories/custom-pages-demo.yaml"


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


def _request(method: str, path: str, body: dict | None = None, timeout: float = 300.0) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{SERVER_BASE}{path}", data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else {})


def _run_scenario() -> None:
    print(f"POST /sessions target_url={TARGET_URL} story={STORY_PATH}")
    status, body = _request("POST", "/sessions", {"target_url": TARGET_URL, "story": STORY_PATH})
    assert status == 201, f"expected 201, got {status}: {body}"
    session_id = body["session_id"]
    print(f"  session_id={session_id}")

    try:
        print("POST /sessions/{id}/run (real AI calls, this will take a while) ...")
        start = time.monotonic()
        status, body = _request("POST", f"/sessions/{session_id}/run")
        elapsed = time.monotonic() - start
        print(f"  status={status} elapsed={elapsed:.1f}s")
        print(f"  passed={body.get('passed')}")
        print(f"  spec_path={body.get('spec_path')}")
        print(f"  failure_notes={body.get('failure_notes')}")
        assert status == 200, f"expected 200, got {status}: {body}"
        assert body.get("passed") is True, f"story did not pass: {body}"
    finally:
        print(f"DELETE /sessions/{session_id}")
        status, _ = _request("DELETE", f"/sessions/{session_id}")
        assert status == 204, f"expected 204, got {status}"

    print("PASS")


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

    if not _port_open(SERVER_HOST, SERVER_PORT):
        print(f"starting session server on :{SERVER_PORT} ...")
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_for_port(SERVER_HOST, SERVER_PORT)
    else:
        print(f"session server already running on :{SERVER_HOST}:{SERVER_PORT}")

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
