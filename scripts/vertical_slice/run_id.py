"""Single source of truth for the `run_id` format used to prefix run-scoped
history log filenames (`{run_id}__{stem}.steps.jsonl` etc, see step_log.py /
task_log.py). Sortable local-time string so a plain directory listing sorts
chronologically across scenarios without parsing filenames.
"""

from __future__ import annotations

from datetime import datetime

RUN_ID_FORMAT = "%Y%m%dT%H%M%S"


def new_run_id() -> str:
    return datetime.now().strftime(RUN_ID_FORMAT)


def parse_run_id_prefix(name: str) -> datetime | None:
    """Extracts and parses the `run_id` prefix from a history filename
    (e.g. `20260719T153012__search-demo.steps.jsonl`). Returns None if
    `name` has no `__` separator or the prefix isn't a valid run_id --
    e.g. pre-run_id legacy logs that predate this module.
    """
    prefix, sep, _ = name.partition("__")
    if not sep:
        return None
    try:
        return datetime.strptime(prefix, RUN_ID_FORMAT)
    except ValueError:
        return None
