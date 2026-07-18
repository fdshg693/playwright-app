"""Diagnostic jsonl logging for `<out>.steps.jsonl`.

One JSON object per step turn (prompt snapshot, raw model output items,
every tool call's arguments/raw CLI output) so a stop reason can be read
back afterwards instead of re-guessed from the console log.
"""

from __future__ import annotations

import json
from pathlib import Path

from .task_log import history_dir

SNAPSHOT_LOG_LIMIT = 2000


def serialize_output_item(item) -> dict:
    if item.type == "function_call":
        return {"type": "function_call", "name": item.name, "arguments": item.arguments}
    if item.type == "reasoning":
        # Reasoning content is encrypted/opaque and carries no diagnostic value;
        # only its presence matters.
        return {"type": "reasoning"}
    data = item.model_dump() if hasattr(item, "model_dump") else {"type": getattr(item, "type", "unknown"), "repr": repr(item)}
    if data.get("encrypted_content"):
        data["encrypted_content"] = f"<omitted, {len(data['encrypted_content'])} chars>"
    return data


def truncate(text: str, limit: int = SNAPSHOT_LOG_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...<truncated, {len(text)} chars total>"


def step_log_path(out_path: str, run_id: str) -> Path:
    stem = Path(out_path).stem
    return history_dir(out_path) / f"{run_id}__{stem}.steps.jsonl"


def append_step_log(entry: dict, out_path: str, run_id: str) -> None:
    path = step_log_path(out_path, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
