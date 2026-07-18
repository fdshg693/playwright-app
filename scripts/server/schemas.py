"""Pydantic request/response models for the session HTTP API.

See plan/main/02-server-skeleton.md: `story` is accepted but only stored,
not interpreted -- consuming it is Step3's responsibility.
"""

from __future__ import annotations

from pydantic import BaseModel


class StartSessionRequest(BaseModel):
    target_url: str
    story: str | None = None


class StartSessionResponse(BaseModel):
    session_id: str


class SnapshotResponse(BaseModel):
    snapshot: str


class CommandRequest(BaseModel):
    command: str
    args: list[str] = []


class CommandResponse(BaseModel):
    generated_code: str | None
    raw_output: str


class RunResponse(BaseModel):
    passed: bool
    spec_path: str
    failure_notes: list[dict] = []
