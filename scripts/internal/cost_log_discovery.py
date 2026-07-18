"""Resolves cost_summary.py CLI path/directory arguments into a concrete list
of `.steps.jsonl` files, and filters that list by a per-file run time.

See [[cost-summary]].
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from scripts.vertical_slice.run_id import parse_run_id_prefix


def discover_log_files(inputs: list[str]) -> list[Path]:
    """Each input that is a directory contributes its `**/*.steps.jsonl`
    (recursive; `*.tasks.jsonl` has no `usage` field and is never matched).
    Each input that is a file is taken as-is. Returns a deduplicated, sorted
    list. Raises SystemExit if an input is neither an existing file nor
    directory."""
    found: set[Path] = set()
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            found.update(path.rglob("*.steps.jsonl"))
        elif path.is_file():
            found.add(path)
        else:
            raise SystemExit(f"not found: {path}")
    return sorted(found)


def resolve_run_time(path: Path) -> datetime:
    """The file's run time: parsed from its `{run_id}__{stem}` filename
    prefix (run_id.parse_run_id_prefix) when present, else the filesystem
    mtime as a fallback for pre-run_id legacy logs."""
    parsed = parse_run_id_prefix(path.name)
    if parsed is not None:
        return parsed
    return datetime.fromtimestamp(path.stat().st_mtime)


def is_run_time_fallback(path: Path) -> bool:
    """True when resolve_run_time(path) had to fall back to mtime. Exposed
    separately (rather than folded into resolve_run_time's return value) so
    callers that only need the time don't have to unpack a tuple, while
    cost_report can still annotate fallback rows for the user."""
    return parse_run_id_prefix(path.name) is None


def filter_by_time_range(paths: list[Path], start: datetime | None, end: datetime | None) -> list[Path]:
    """Keep only paths whose resolve_run_time() falls within [start, end]
    (a None bound is unbounded on that side). Filtering is file-grained, not
    per-entry: one run time per file, matching the one-file-per-execution
    convention set up in [[vertical-slice-runner]]."""
    result = []
    for path in paths:
        t = resolve_run_time(path)
        if start is not None and t < start:
            continue
        if end is not None and t > end:
            continue
        result.append(path)
    return result
