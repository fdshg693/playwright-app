"""Real-AI smoke test for Step7: POST /sessions/{id}/stop + resume.

Drives the session server's `/run` endpoint in a background thread against a
real, billed AI API, calls `POST /sessions/{id}/stop` a few seconds in, and
confirms the run comes back with `passed=False` and exactly one
`failure_notes` entry with `reason="stopped"` for the step that was left
unattempted. Then reconstructs the `tasks_log` path from `spec_path` + `run_id`
(the same command-style reconstruction any external `/sessions/resume`
caller has to do -- see task_log.task_log_path/history_dir and
.claude/rules/vertical-slice-runner.md) and resumes from the stopped step,
confirming the story completes (`passed=True`).

Unlike scripts/temp/test_server_ai_run.py (which runs a story to completion
in one shot), this exercises the stop signal added in Step7
(.claude/plan/main/07-human-observation-and-control.md) -- `SessionManager`'s
per-session `threading.Event`, and the step/retry-boundary checks in
scripts/vertical_slice/runner.run_steps()/run_task_logged_step().

Starts the custom-pages nginx (:8080) and the session server (:8000)
themselves if they aren't already running, and only stops the ones it
started (same as test_server_ai_run.py).

Run with:

    uv run python scripts/temp/test_server_stop_resume.py
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
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
TARGET_URL = f"http://localhost:{PAGES_PORT}/wizard-step1.html"
STORY_PATH = "scripts/stories/wizard-demo.yaml"
# wizard-demo.yaml has 8 simple form-filling steps; a handful of seconds is
# enough for the AI loop to complete at least the first step or two before
# /stop is called, without needing exact step-timing control.
STOP_AFTER_SECONDS = 8.0


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

    resume_session_id: str | None = None
    try:
        run_result: dict = {}

        def _do_run() -> None:
            run_status, run_body = _request("POST", f"/sessions/{session_id}/run")
            run_result["status"] = run_status
            run_result["body"] = run_body

        run_thread = threading.Thread(target=_do_run)

        print("POST /sessions/{id}/run in background thread (real AI calls, this will take a while) ...")
        start = time.monotonic()
        run_thread.start()

        print(f"  waiting {STOP_AFTER_SECONDS}s before stopping ...")
        time.sleep(STOP_AFTER_SECONDS)

        print(f"POST /sessions/{session_id}/stop")
        stop_status, stop_body = _request("POST", f"/sessions/{session_id}/stop")
        assert stop_status == 200, f"expected 200, got {stop_status}: {stop_body}"
        assert stop_body.get("stop_requested") is True, f"unexpected stop response: {stop_body}"

        run_thread.join()
        elapsed = time.monotonic() - start
        run_status = run_result["status"]
        run_body = run_result["body"]
        print(f"  /run finished after {elapsed:.1f}s status={run_status}")
        print(f"  passed={run_body.get('passed')}")
        print(f"  spec_path={run_body.get('spec_path')}")
        print(f"  failure_notes={run_body.get('failure_notes')}")
        assert run_status == 200, f"expected 200, got {run_status}: {run_body}"
        assert run_body.get("passed") is False, f"expected the run to be stopped, got: {run_body}"

        failure_notes = run_body.get("failure_notes") or []
        stopped_notes = [note for note in failure_notes if note.get("reason") == "stopped"]
        assert len(stopped_notes) == 1, f"expected exactly one reason=stopped note, got: {failure_notes}"
        stopped_step_id = stopped_notes[0]["step"]
        print(f"  stopped before step {stopped_step_id}")

        run_id = run_body["run_id"]
        spec_path = Path(run_body["spec_path"])
        # Mechanical reconstruction of the tasks_log path from spec_path +
        # run_id, per task_log.history_dir()/task_log_path()'s naming
        # convention (.claude/rules/vertical-slice-runner.md) -- the same
        # thing any external /sessions/resume caller has to do, since
        # ResumeResponse/RunResponse don't carry tasks_log directly.
        tasks_log = spec_path.parent / f"{spec_path.stem}.history" / f"{run_id}__{spec_path.stem}.tasks.jsonl"
        print(f"  checking {tasks_log} has no entry for the stopped step ...")
        assert tasks_log.exists(), f"expected tasks log to exist: {tasks_log}"
        with tasks_log.open(encoding="utf-8") as f:
            logged_step_ids = [json.loads(line)["step_id"] for line in f if line.strip()]
        assert stopped_step_id not in logged_step_ids, (
            f"stopped step {stopped_step_id} should not be logged, got: {logged_step_ids}"
        )

        print(f"POST /sessions/resume resume_before_step={stopped_step_id} tasks_log={tasks_log}")
        resume_status, resume_body = _request(
            "POST",
            "/sessions/resume",
            {"tasks_log": str(tasks_log), "resume_before_step": stopped_step_id, "story": STORY_PATH},
        )
        print(f"  status={resume_status}")
        print(f"  passed={resume_body.get('passed')}")
        print(f"  failure_notes={resume_body.get('failure_notes')}")
        assert resume_status == 201, f"expected 201, got {resume_status}: {resume_body}"
        assert resume_body.get("passed") is True, f"resumed story did not pass: {resume_body}"
        resume_session_id = resume_body["session_id"]
    finally:
        print(f"DELETE /sessions/{session_id}")
        status, _ = _request("DELETE", f"/sessions/{session_id}")
        assert status == 204, f"expected 204, got {status}"
        if resume_session_id is not None:
            print(f"DELETE /sessions/{resume_session_id}")
            status, _ = _request("DELETE", f"/sessions/{resume_session_id}")
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
