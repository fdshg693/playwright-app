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

from openai import OpenAI

from scripts.vertical_slice.cli_executor import CliExecutor
from scripts.vertical_slice.runner import StepBlock, run_playwright_test, write_failure_notes, write_spec_file
from scripts.vertical_slice.step_log import step_log_path
from scripts.vertical_slice.step_runner import run_step
from scripts.vertical_slice.story import Story

logger = logging.getLogger("session_server")


def run_story(
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    story: Story,
    out_path: str,
    seed_code: str | None = None,
) -> tuple[bool, str, list[dict]]:
    """Run every step of `story` in order, then write and test the artifacts.

    `seed_code` is the generated code for the `POST /sessions` navigation to
    `target_url`, captured by the caller before this function ever sees the
    session (that navigation isn't a story step, so it can't be recovered
    from `story.steps`). Without it the assembled spec file would start
    in-place on whatever page the AI left off on, instead of navigating
    there itself, and fail the moment it's run standalone.

    Returns (passed, spec_path, failure_notes). Stops at the first step that
    produces failure_notes, same as `runner.run_vertical_slice()`.
    """
    blocks: list[StepBlock] = []
    failure_notes: list[dict] = []
    step_log_path(out_path).unlink(missing_ok=True)

    if seed_code:
        blocks.append(StepBlock(step=None, code=[seed_code]))

    for i, step in enumerate(story.steps):
        logger.info("=== step %s: %s ===", step.id, step.instruction)
        step_code, step_failures = run_step(cli, client, model, step, story.steps[i:], out_path)
        blocks.append(StepBlock(step=step, code=step_code))
        failure_notes.extend(step_failures)
        if step_failures:
            break
    else:
        logger.info("all steps completed")

    spec_path = write_spec_file(blocks, out_path, story.name)
    write_failure_notes(failure_notes, out_path)

    if failure_notes:
        logger.warning("stopped early with failure notes; skipping npx playwright test")
        return False, str(spec_path), failure_notes

    passed = run_playwright_test(spec_path)
    logger.info("npx playwright test %s", "passed" if passed else "failed")
    return passed, str(spec_path), failure_notes
