"""Story-level orchestration for the session server (Step3).

Reuses Step1's `step_runner.run_step` and `runner.write_spec_file` /
`runner.write_failure_notes` / `runner.run_playwright_test` as-is -- only the
loop-over-steps assembly is new here. `runner.run_vertical_slice()` itself is
not reused because it opens `story.seed_url` unconditionally, but the server
has already navigated via `POST /sessions`' `target_url`
(plan/main/03-task-orchestration.md decision table).
"""

from __future__ import annotations

import logging
from typing import Callable

from openai import OpenAI

from scripts.vertical_slice import runner
from scripts.vertical_slice.cli_executor import CliExecutor
from scripts.vertical_slice.run_id import new_run_id
from scripts.vertical_slice.runner import StepBlock
from scripts.vertical_slice.story import Story

logger = logging.getLogger("session_server")


def run_story(
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    story: Story,
    out_path: str,
    seed_code: str | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[bool, str, list[dict], str]:
    """Run every step of `story` in order, then write and test the artifacts.

    `seed_code` is the generated code for the `POST /sessions` navigation to
    `target_url`, captured by the caller before this function ever sees the
    session (that navigation isn't a story step, so it can't be recovered
    from `story.steps`). Without it the assembled spec file would start
    in-place on whatever page the AI left off on, instead of navigating
    there itself, and fail the moment it's run standalone.

    `should_stop` is passed straight through to `runner.run_steps()` (Step7).
    This function doesn't know or care where it comes from -- `app.py` wires
    it to `SessionManager.is_stop_requested`, but any zero-arg callable
    returning bool works.

    Returns (passed, spec_path, failure_notes, run_id). Stops at the first
    step that produces failure_notes, same as `runner.run_vertical_slice()`.
    """
    run_id = new_run_id()

    seed_block: list[StepBlock] = []
    if seed_code:
        seed_block.append(StepBlock(step=None, code=[seed_code]))
        runner.log_seed_task(cli, seed_code, out_path, run_id)

    step_blocks, failure_notes = runner.run_steps(
        story.steps, cli, client, model, out_path, run_id, should_stop=should_stop
    )
    passed, spec_path = runner.write_and_test(seed_block + step_blocks, failure_notes, out_path, story.name)
    return passed, str(spec_path), failure_notes, run_id


def resume_story(
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    story: Story,
    out_path: str,
    tasks_log_path: str,
    resume_before_step: int,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[bool, str, list[dict], str]:
    """Server-side counterpart of `runner.resume_vertical_slice`: fast-forwards
    `cli` (a fresh session from `SessionManager.create()`, which never
    navigates) using the code recorded in `tasks_log_path`, then runs
    `story.steps` in order from there. See `runner.build_resume_state` for
    the replay logic shared with the CLI entry point.

    `should_stop` is passed straight through to `runner.run_steps()`, same as
    `run_story` above.
    """
    replay_source, prior_blocks = runner.build_resume_state(tasks_log_path, resume_before_step)

    cli.open()
    if replay_source:
        cli.run_code(replay_source)

    run_id = new_run_id()

    step_blocks, failure_notes = runner.run_steps(
        story.steps, cli, client, model, out_path, run_id, should_stop=should_stop
    )
    passed, spec_path = runner.write_and_test(prior_blocks + step_blocks, failure_notes, out_path, story.name)
    return passed, str(spec_path), failure_notes, run_id
