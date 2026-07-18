"""FastAPI app: the network-server cut of Step1's CliExecutor boundary.

Keeps one playwright-cli session alive per session_id and exposes the
operations plan/main/02-server-skeleton.md (snapshot/command, human-driven)
and plan/main/03-task-orchestration.md (`/run`, AI-driven) call for.
`/command` passes `command`/`args` straight through to `CliExecutor.execute`
without going through the tool-schema layer in vertical_slice/tools.py.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from openai import OpenAI

from scripts.vertical_slice import config
from scripts.vertical_slice.cli_executor import CliError

from . import orchestrator
from .schemas import (
    CommandRequest,
    CommandResponse,
    ResumeRequest,
    ResumeResponse,
    RunResponse,
    SnapshotResponse,
    StartSessionRequest,
    StartSessionResponse,
)
from .session_manager import SessionManager, SessionNotFoundError

app = FastAPI(title="playwright-app session server")
sessions = SessionManager()

# Lazy singleton: config.get_api_key() raises if OPENAI_API_KEY is unset, so
# building this at import time would make AI-free endpoints (/snapshot,
# /command) unable to start the server without an API key.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.get_api_key(), base_url=config.get_base_url())
    return _client


@app.post("/sessions", status_code=201)
def start_session(body: StartSessionRequest) -> StartSessionResponse:
    session_id = uuid.uuid4().hex
    cli = sessions.create(session_id, story=body.story)
    try:
        open_result = cli.open(body.target_url)
    except CliError as exc:
        sessions.close(session_id)
        raise HTTPException(status_code=502, detail=str(exc)) from None
    sessions.set_seed_code(session_id, open_result.generated_code)
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


@app.post("/sessions/{session_id}/run")
def run_session(session_id: str) -> RunResponse:
    cli = _get_cli(session_id)
    story = sessions.get_story(session_id)
    if story is None:
        raise HTTPException(status_code=400, detail=f"session {session_id} has no story to run")

    out_path = f"tests/generated/{story.name}.spec.ts"
    passed, spec_path, failure_notes = orchestrator.run_story(
        cli, _get_client(), config.get_model(), story, out_path, seed_code=sessions.get_seed_code(session_id)
    )
    return RunResponse(passed=passed, spec_path=spec_path, failure_notes=failure_notes)


@app.post("/sessions/resume", status_code=201)
def resume_session(body: ResumeRequest) -> ResumeResponse:
    # Mirrors start_session's create-then-drive shape, but the new session is
    # never navigated: resume_story fast-forwards it from tasks_log itself
    # (plan/main/05-recording-and-resume.md), same as a fresh CliExecutor
    # never having called open() until resume_story does.
    session_id = uuid.uuid4().hex
    cli = sessions.create(session_id, story=body.story)
    story = sessions.get_story(session_id)
    if story is None:
        sessions.close(session_id)
        raise HTTPException(status_code=400, detail="resume requires a story")

    out_path = f"tests/generated/{story.name}.spec.ts"
    try:
        passed, spec_path, failure_notes = orchestrator.resume_story(
            cli, _get_client(), config.get_model(), story, out_path, body.tasks_log, body.resume_before_step
        )
    except CliError as exc:
        sessions.close(session_id)
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return ResumeResponse(session_id=session_id, passed=passed, spec_path=spec_path, failure_notes=failure_notes)


@app.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: str) -> None:
    _get_cli(session_id)  # 404s before closing if the id is unknown
    sessions.close(session_id)


def _get_cli(session_id: str):
    try:
        return sessions.get(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown session_id: {session_id}") from None
