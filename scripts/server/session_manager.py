"""In-memory registry of session_id -> CliExecutor.

session_id is the playwright-cli `-s=` session name itself, per the
plan's decision to not introduce a separate "run" concept (see
plan/main/02-server-skeleton.md). Concurrent access safety across multiple
HTTP requests to the *same* session is still out of scope (Step2). Step8
(plan/main/08-safety-guardrails.md) adds a `threading.Lock` around just
`create()`/`close()`, because those are the only places where a
background thread (the idle-session sweep) mutates the registry
independently of any HTTP request -- a qualitatively different concern
from the request-vs-request races Step2 waived. Read-only accessors
(`get()`/`is_stop_requested()`/etc.) remain unlocked.

`story` is interpreted here (plan/main/03-task-orchestration.md): the
string passed to `create()` is a story YAML file path, parsed eagerly via
`story.load_story()` and kept as a `Story` for `/run` to consume later.
"""

from __future__ import annotations

import logging
import threading
import time

from scripts.vertical_slice.cli_executor import CliExecutor
from scripts.vertical_slice.story import Story, load_story

logger = logging.getLogger("session_server")

# How often the idle-session sweep wakes up and scans _last_activity. An
# implementation-detail knob (it only affects how far past
# idle_timeout_seconds a session can survive before being noticed), not an
# operator-facing setting -- hardcoded rather than env-configurable, same
# YAGNI stance as MAX_STEP_ATTEMPTS.
_SWEEP_INTERVAL_SECONDS = 5.0


class SessionNotFoundError(KeyError):
    """Raised when a session_id has no live CliExecutor."""


class SessionLimitExceededError(RuntimeError):
    """Raised by create() when max_sessions live sessions already exist."""


class SessionManager:
    def __init__(
        self,
        max_sessions: int = 5,
        idle_timeout_seconds: float = 1800.0,
        allowed_domains: list[str] | None = None,
    ) -> None:
        self._max_sessions = max_sessions
        self._idle_timeout_seconds = idle_timeout_seconds
        self._allowed_domains = allowed_domains

        self._sessions: dict[str, CliExecutor] = {}
        self._stories: dict[str, Story | None] = {}
        self._seed_code: dict[str, str | None] = {}
        self._stop_flags: dict[str, threading.Event] = {}
        self._last_activity: dict[str, float] = {}

        # Guards create()/close() only (both the foreground DELETE path and
        # the background sweep's close() calls) -- see module docstring.
        self._lock = threading.Lock()

        self._sweep_thread = threading.Thread(target=self._sweep_loop, daemon=True)
        self._sweep_thread.start()

    def create(self, session_id: str, story: str | None = None) -> CliExecutor:
        with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise SessionLimitExceededError(
                    f"max_sessions={self._max_sessions} concurrent sessions already active"
                )
            cli = CliExecutor(session=session_id, allowed_domains=self._allowed_domains)
            self._sessions[session_id] = cli
            self._stories[session_id] = load_story(story) if story else None
            self._seed_code[session_id] = None
            self._stop_flags[session_id] = threading.Event()
            self._last_activity[session_id] = time.monotonic()
            return cli

    def get(self, session_id: str) -> CliExecutor:
        try:
            cli = self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None
        self._last_activity[session_id] = time.monotonic()
        return cli

    def get_story(self, session_id: str) -> Story | None:
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        return self._stories[session_id]

    def set_seed_code(self, session_id: str, code: str | None) -> None:
        """Record the generated code for the `POST /sessions` navigation, so
        `/run` can prepend it to the assembled spec file (it happens outside
        `run_story`'s step loop, since it's driven by `target_url`, not a
        story step -- see plan/main/03-task-orchestration.md)."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        self._seed_code[session_id] = code

    def get_seed_code(self, session_id: str) -> str | None:
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        return self._seed_code[session_id]

    def close(self, session_id: str) -> None:
        with self._lock:
            self._close_locked(session_id)

    def _close_locked(self, session_id: str) -> None:
        """close() body, assumed to run under self._lock (held by close()
        itself or by _sweep_idle())."""
        try:
            cli = self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None
        cli.close()
        del self._sessions[session_id]
        del self._stories[session_id]
        del self._seed_code[session_id]
        del self._stop_flags[session_id]
        del self._last_activity[session_id]

    def request_stop(self, session_id: str) -> None:
        """Sets the stop flag for `session_id`, an asynchronous signal that
        `runner.run_steps`/`run_task_logged_step` poll at step/retry
        boundaries (see is_stop_requested). Does not itself wait for a
        running `/run`/`/sessions/resume` to observe it."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        self._stop_flags[session_id].set()

    def is_stop_requested(self, session_id: str) -> bool:
        """Checks the stop flag *and* records this call as activity (Step8):
        `runner.run_steps`/`run_task_logged_step` already call this at every
        step/retry boundary (Step7), so piggybacking activity-tracking here
        covers long-running `/run`/`/sessions/resume` calls without adding a
        new touch point to runner.py/step_runner.py."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        self._last_activity[session_id] = time.monotonic()
        return self._stop_flags[session_id].is_set()

    def _sweep_idle(self) -> None:
        with self._lock:
            now = time.monotonic()
            expired = [
                session_id
                for session_id, last_active in self._last_activity.items()
                if now - last_active > self._idle_timeout_seconds
            ]
            for session_id in expired:
                logger.info("closing idle session %s (no activity for >%ss)", session_id, self._idle_timeout_seconds)
                self._close_locked(session_id)

    def _sweep_loop(self) -> None:
        while True:
            time.sleep(_SWEEP_INTERVAL_SECONDS)
            try:
                self._sweep_idle()
            except Exception:
                logger.exception("idle-session sweep failed")
