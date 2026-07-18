"""FastAPI app: the network-server cut of Step1's CliExecutor boundary.

Keeps one playwright-cli session alive per session_id and exposes the four
operations plan/main/02-server-skeleton.md calls for. No AI orchestration
here (Step3) -- a human drives these endpoints directly. `/command` passes
`command`/`args` straight through to `CliExecutor.execute` without going
through the tool-schema layer in vertical_slice/tools.py.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException

from scripts.vertical_slice.cli_executor import CliError

from .schemas import (
    CommandRequest,
    CommandResponse,
    SnapshotResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from .session_manager import SessionManager, SessionNotFoundError

app = FastAPI(title="playwright-app session server")
sessions = SessionManager()


@app.post("/sessions", status_code=201)
def start_session(body: StartSessionRequest) -> StartSessionResponse:
    session_id = uuid.uuid4().hex
    cli = sessions.create(session_id, story=body.story)
    try:
        cli.open(body.target_url)
    except CliError as exc:
        sessions.close(session_id)
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return StartSessionResponse(session_id=session_id)


@app.get("/sessions/{session_id}/snapshot")
def get_snapshot(session_id: str) -> SnapshotResponse:
    cli = _get_cli(session_id)
    try:
        return SnapshotResponse(snapshot=cli.snapshot_text())
    except CliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None


@app.post("/sessions/{session_id}/command")
def run_command(session_id: str, body: CommandRequest) -> CommandResponse:
    cli = _get_cli(session_id)
    try:
        result = cli.execute(body.command, body.args)
    except CliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return CommandResponse(generated_code=result.generated_code, raw_output=result.raw_output)


@app.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: str) -> None:
    _get_cli(session_id)  # 404s before closing if the id is unknown
    sessions.close(session_id)


def _get_cli(session_id: str):
    try:
        return sessions.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown session_id: {session_id}") from None
