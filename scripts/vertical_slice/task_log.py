"""Serialization for `<out>.tasks.jsonl`: one JSON object per task (a story
step, or the initial seed navigation), holding what's needed to replay the
browser up to that task and to inspect what happened there.

Separate from `<out>.steps.jsonl` (step_log.py), which is the AI turn-level
diagnostic log -- reconstructing "the code a task produced" from that file
would mean re-parsing every turn's tool_results. Here each entry already is
one task's worth of replayable code plus its before/after snapshot and
screenshot.

Entries also carry an "attempts" field (Step6): 1 means the task's step
succeeded on the first try, 2 or more means `runner.run_task_logged_step`
retried before finishing -- `code` is still the concatenation of every
attempt's generated code, in attempt order.
"""

from __future__ import annotations

import json
from pathlib import Path


def history_dir(out_path: str) -> Path:
    """Run-scoped log directory for `out_path`, e.g.
    `tests/generated/search-demo.spec.ts` -> `tests/generated/search-demo.history/`.
    Holds every run's `{run_id}__{stem}.steps.jsonl`/`.tasks.jsonl`, kept out
    of `tests/generated/` directly so that dir stays "current state" only."""
    path = Path(out_path)
    return path.parent / f"{path.stem}.history"


def task_log_path(out_path: str, run_id: str) -> Path:
    stem = Path(out_path).stem
    return history_dir(out_path) / f"{run_id}__{stem}.tasks.jsonl"


def recordings_dir(out_path: str) -> Path:
    """Screenshot directory for `out_path`, e.g. `tests/generated/search-demo.spec.ts`
    -> `tests/generated/search-demo.recordings/`."""
    path = Path(out_path)
    return path.parent / f"{path.stem}.recordings"


def append_task_log(entry: dict, out_path: str, run_id: str) -> None:
    path = task_log_path(out_path, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_task_log(path: str | Path) -> list[dict]:
    entries: list[dict] = []
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def build_replay_source(entries: list[dict], before_step: int) -> str:
    """Concatenate the `code` of every entry whose `step_id` is None (the
    seed block) or less than `before_step`, into the single function
    expression `CliExecutor.run_code` expects.

    `await expect(...)` lines are dropped: `run-code` executes in a bare
    `async page => { ... }` sandbox with only `page` injected, so `expect` is
    undefined there (references/running-code.md). Assertions are read-only
    and don't affect browser state, so skipping them during replay is safe --
    they still appear in full in the entries themselves, for `prior_blocks`.

    Returns "" (not a wrapped no-op function) when there is nothing to
    replay, so callers can skip the `run_code` call entirely.
    """
    lines: list[str] = []
    for entry in entries:
        step_id = entry.get("step_id")
        if step_id is not None and step_id >= before_step:
            continue
        for code in entry.get("code", []):
            for line in code.splitlines():
                line = line.strip()
                if line and not line.startswith("await expect("):
                    lines.append(line)

    if not lines:
        return ""

    body = "\n".join(f"  {line}" for line in lines)
    return f"async page => {{\n{body}\n}}"
