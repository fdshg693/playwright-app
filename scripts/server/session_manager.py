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

from scripts.vertical_slice.cli_executor import CliExecutor
from scripts.vertical_slice.story import Story, load_story


class SessionNotFoundError(KeyError):
    """Raised when a session_id has no live CliExecutor."""


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, CliExecutor] = {}
        self._stories: dict[str, Story | None] = {}

    def create(self, session_id: str, story: str | None = None) -> CliExecutor:
        cli = CliExecutor(session=session_id)
        self._sessions[session_id] = cli
        self._stories[session_id] = load_story(story) if story else None
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

    def close(self, session_id: str) -> None:
        cli = self.get(session_id)
        cli.close()
        del self._sessions[session_id]
        del self._stories[session_id]
