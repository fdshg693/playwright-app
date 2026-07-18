"""Story-level orchestration: run every step in order, then write the
generated artifacts (`<out>.spec.ts`, `<out>.failure-notes.json`) and run the
resulting spec through `npx playwright test`.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from . import task_log
from .cli_executor import CliExecutor
from .run_id import new_run_id
from .step_runner import run_step
from .story import Step, Story

logger = logging.getLogger("vertical_slice")


@dataclass
class StepBlock:
    """One chunk of generated code, tagged with the story step it came from.

    `step` is None for the initial `cli.open(story.seed_url)` block -- it has
    no story step number, so `write_spec_file` skips the `// N. ...` comment
    for it (test-generation.md 2.2 only numbers actual story steps).
    """

    step: Step | None
    code: list[str]


def write_spec_file(blocks: list[StepBlock], out_path: str, test_name: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    body_lines: list[str] = []
    for block in blocks:
        lines = [line for code in block.code for line in code.splitlines() if line.strip()]
        if not lines:
            continue
        if block.step is not None:
            body_lines.append(f"// {block.step.id}. {block.step.instruction}")
        body_lines.extend(lines)

    body = "\n".join(f"  {line}" for line in body_lines)
    content = (
        "import { test, expect } from '@playwright/test';\n\n"
        f"test('{test_name}', async ({{ page }}) => {{\n"
        f"{body}\n"
        "});\n"
    )
    path.write_text(content, encoding="utf-8")
    logger.info("spec file written to %s", path)
    return path


def write_failure_notes(failure_notes: list[dict], out_path: str) -> None:
    if not failure_notes:
        return
    path = Path(out_path).with_suffix(".failure-notes.json")
    path.write_text(json.dumps(failure_notes, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.warning("failure notes written to %s", path)


def run_playwright_test(spec_path: Path) -> bool:
    proc = subprocess.run(
        ["npx", "playwright", "test", str(spec_path)], capture_output=True, text=True
    )
    logger.info("npx playwright test output:\n%s", proc.stdout + proc.stderr)
    return proc.returncode == 0


def log_seed_task(cli: CliExecutor, code: str | None, out_path: str, run_id: str) -> None:
    """Records the `<out>.tasks.jsonl` entry for the initial navigation (the
    `cli.open(story.seed_url)` call, or -- for resume -- the bare
    `cli.open()` + replay). There's no "before" state to capture: the
    browser session doesn't exist until `open()` returns.
    """
    recordings = task_log.recordings_dir(out_path)
    recordings.mkdir(parents=True, exist_ok=True)
    task_log.append_task_log(
        {
            "step_id": None,
            "instruction": None,
            "code": [code] if code else [],
            "success": True,
            "before_snapshot": None,
            "after_snapshot": cli.snapshot_text(),
            "before_screenshot": None,
            "after_screenshot": cli.screenshot(str(recordings / "seed-after.png")),
        },
        out_path,
        run_id,
    )


def run_task_logged_step(
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    step: Step,
    remaining_steps: list[Step],
    out_path: str,
    run_id: str,
) -> tuple[list[str], list[dict]]:
    """Runs one step via `step_runner.run_step`, wrapped with before/after
    snapshot+screenshot capture and a `<out>.tasks.jsonl` entry (task_log.py).
    Kept outside `step_runner.run_step` itself so its turn-control loop stays
    untouched (plan/main/05-recording-and-resume.md decision table).
    """
    recordings = task_log.recordings_dir(out_path)
    recordings.mkdir(parents=True, exist_ok=True)

    before_snapshot = cli.snapshot_text()
    before_screenshot = cli.screenshot(str(recordings / f"{step.id}-before.png"))

    step_code, step_failures = run_step(cli, client, model, step, remaining_steps, out_path, run_id)

    after_snapshot = cli.snapshot_text()
    after_screenshot = cli.screenshot(str(recordings / f"{step.id}-after.png"))

    task_log.append_task_log(
        {
            "step_id": step.id,
            "instruction": step.instruction,
            "code": step_code,
            "success": not step_failures,
            "before_snapshot": before_snapshot,
            "after_snapshot": after_snapshot,
            "before_screenshot": before_screenshot,
            "after_screenshot": after_screenshot,
        },
        out_path,
        run_id,
    )
    return step_code, step_failures


def run_steps(
    story_steps: list[Step], cli: CliExecutor, client: OpenAI, model: str, out_path: str, run_id: str
) -> tuple[list[StepBlock], list[dict]]:
    """Runs `story_steps` in order, stopping at the first step that produces
    failure_notes. Shared by run_vertical_slice/resume_vertical_slice here
    and orchestrator.run_story/resume_story, so all four entry points record
    and assemble tasks identically.
    """
    blocks: list[StepBlock] = []
    failure_notes: list[dict] = []
    for i, step in enumerate(story_steps):
        logger.info("=== step %s: %s ===", step.id, step.instruction)
        step_code, step_failures = run_task_logged_step(
            cli, client, model, step, story_steps[i:], out_path, run_id
        )
        blocks.append(StepBlock(step=step, code=step_code))
        failure_notes.extend(step_failures)
        if step_failures:
            break
    else:
        logger.info("all steps completed")
    return blocks, failure_notes


def build_resume_state(tasks_log_path: str, resume_before_step: int) -> tuple[str, list[StepBlock]]:
    """Loads `tasks_log_path` and returns (replay_source, prior_blocks):

    - `replay_source`: the `run-code` source (task_log.build_replay_source)
      to fast-forward a *new* browser session up to `resume_before_step`, or
      "" if there's nothing to replay.
    - `prior_blocks`: the same tasks reconstructed as `StepBlock`s (with
      their original code, assertions included) for prepending to a freshly
      assembled `.spec.ts` -- unlike `replay_source`, these are not filtered
      for `run-code` compatibility.

    Does no CLI I/O itself. Callers set up the browser session differently
    (runner.resume_vertical_slice always opens a bare new session;
    orchestrator.resume_story's session comes from a `SessionManager.create()`
    call that also never navigates), so fast-forwarding is left to them.
    """
    entries = task_log.load_task_log(tasks_log_path)
    replay_source = task_log.build_replay_source(entries, resume_before_step)
    prior_blocks = [
        StepBlock(
            step=Step(id=entry["step_id"], instruction=entry["instruction"])
            if entry["step_id"] is not None
            else None,
            code=entry["code"],
        )
        for entry in entries
        if entry["step_id"] is None or entry["step_id"] < resume_before_step
    ]
    return replay_source, prior_blocks


def write_and_test(
    blocks: list[StepBlock], failure_notes: list[dict], out_path: str, test_name: str
) -> tuple[bool, Path]:
    """Writes `<out>.spec.ts`/`.failure-notes.json` and, absent failures, runs
    it through `npx playwright test`. Shared by all four entry points
    (run/resume x vertical_slice/orchestrator) -- they differ only in what
    else they return alongside `passed`.
    """
    spec_path = write_spec_file(blocks, out_path, test_name)
    write_failure_notes(failure_notes, out_path)

    if failure_notes:
        logger.warning("stopped early with failure notes; skipping npx playwright test")
        return False, spec_path

    passed = run_playwright_test(spec_path)
    logger.info("npx playwright test %s", "passed" if passed else "failed")
    return passed, spec_path


def run_vertical_slice(
    story: Story, cli: CliExecutor, client: OpenAI, model: str, out_path: str
) -> tuple[bool, str]:
    run_id = new_run_id()

    open_result = cli.open(story.seed_url)
    seed_block = [StepBlock(step=None, code=[open_result.generated_code])] if open_result.generated_code else []
    log_seed_task(cli, open_result.generated_code, out_path, run_id)

    step_blocks, failure_notes = run_steps(story.steps, cli, client, model, out_path, run_id)
    passed, _ = write_and_test(seed_block + step_blocks, failure_notes, out_path, story.name)
    return passed, run_id


def resume_vertical_slice(
    story: Story,
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    out_path: str,
    tasks_log_path: str,
    resume_before_step: int,
) -> tuple[bool, str]:
    """Fast-forwards a fresh `cli` session to `resume_before_step` using the
    code recorded in `tasks_log_path`, then runs `story.steps` in order from
    there (see build_resume_state for what "fast-forward" means). `story` can
    be a different YAML than the one that produced `tasks_log_path` -- e.g. a
    branch scenario -- since replay only needs code, not the original story's
    step ids/instructions (plan/main/05-recording-and-resume.md).
    """
    replay_source, prior_blocks = build_resume_state(tasks_log_path, resume_before_step)

    cli.open()
    if replay_source:
        cli.run_code(replay_source)

    run_id = new_run_id()

    step_blocks, failure_notes = run_steps(story.steps, cli, client, model, out_path, run_id)
    passed, _ = write_and_test(prior_blocks + step_blocks, failure_notes, out_path, story.name)
    return passed, run_id
