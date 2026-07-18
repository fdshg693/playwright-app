"""In-memory registry of session_id -> CliExecutor.

session_id is the playwright-cli `-s=` session name itself, per the
plan's decision to not introduce a separate "run" concept (see
plan/main/02-server-skeleton.md). No concurrency locking: Step2's scope
is a single sequential scenario, not concurrent access safety.

`story` is interpreted here (plan/main/03-task-orchestration.md): the
string passed to `create()` is a story YAML file path, parsed eagerly via
`story.load_story()` and kept as a `Story` for `/run` to consume later.
"""

from __future__ import annotations

import threading

from scripts.vertical_slice.cli_executor import CliExecutor
from scripts.vertical_slice.story import Story, load_story


class SessionNotFoundError(KeyError):
    """Raised when a session_id has no live CliExecutor."""


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, CliExecutor] = {}
        self._stories: dict[str, Story | None] = {}
        self._seed_code: dict[str, str | None] = {}
        self._stop_flags: dict[str, threading.Event] = {}

    def create(self, session_id: str, story: str | None = None) -> CliExecutor:
        cli = CliExecutor(session=session_id)
        self._sessions[session_id] = cli
        self._stories[session_id] = load_story(story) if story else None
        self._seed_code[session_id] = None
        self._stop_flags[session_id] = threading.Event()
        return cli

    def get(self, session_id: str) -> CliExecutor:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(session_id) from None

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
        cli = self.get(session_id)
        cli.close()
        del self._sessions[session_id]
        del self._stories[session_id]
        del self._seed_code[session_id]
        del self._stop_flags[session_id]

    def request_stop(self, session_id: str) -> None:
        """Sets the stop flag for `session_id`, an asynchronous signal that
        `runner.run_steps`/`run_task_logged_step` poll at step/retry
        boundaries (see is_stop_requested). Does not itself wait for a
        running `/run`/`/sessions/resume` to observe it."""
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        self._stop_flags[session_id].set()

    def is_stop_requested(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            raise SessionNotFoundError(session_id)
        return self._stop_flags[session_id].is_set()
