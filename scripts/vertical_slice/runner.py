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
from typing import Callable

from openai import OpenAI

from . import task_log
from .cli_executor import CliError, CliExecutor
from .run_id import new_run_id
from .step_log import truncate
from .step_runner import run_step
from .story import Step, Story

logger = logging.getLogger("vertical_slice")

# Retry cap for a single step's attempts (Step6). Pairs with
# step_runner.MAX_TURNS_PER_STEP, which bounds the turns *within* one
# attempt -- this bounds how many fresh attempts run_task_logged_step makes.
# A small hardcoded value per SPEC.md 9章 Open Question / big_plans: start
# small, tune later, no CLI/env override yet (YAGNI).
MAX_STEP_ATTEMPTS = 3

# Machine explanations of what each step_runner.run_step failure `reason`
# means -- not a diagnosis of *why* it happened (SPEC.md 6章 / heal.md 3.4節:
# that judgment call is left to a human, never inferred by another AI call).
FAILURE_REASON_HINTS: dict[str, str] = {
    "cli_error": "A playwright-cli command reported an error (CliError) while executing a tool call.",
    "blocked": "The model itself called finish_step(status=\"blocked\"), declaring it could not complete the step.",
    "no_tool_call": "The model's response contained no tool call even though a tool call was required.",
    "max_turns_exceeded": "The step reached MAX_TURNS_PER_STEP turns without the model calling finish_step.",
    "stopped": "The run was stopped via an external stop request before this step started.",
    "disallowed_url": "A tool call navigated to a host not in ALLOWED_DOMAINS (DisallowedNavigationError).",
}


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


def _capture_or_placeholder(fetch, label: str) -> str:
    """Runs `fetch` (`cli.snapshot_text`/a `cli.screenshot(...)` thunk) for the
    before/after task-log bookkeeping, substituting a placeholder string on
    `CliError` instead of propagating it. The browser can still be stuck in a
    state `snapshot`/`screenshot` can't handle (e.g. an open file-chooser
    modal) even after `run_step` has already stopped and returned
    failure_notes for it -- this call happens unconditionally around that,
    and must not itself crash the run.
    """
    try:
        return fetch()
    except CliError as exc:
        return f"<{label} unavailable: {exc}>"


def _capture_diagnostic(fetch) -> str | dict:
    """Runs `fetch` (`cli.console`/`cli.requests`) and truncates the result
    like the `snapshot` diagnostic. A `CliError` here is a failure of the
    diagnostic capture itself, not of the step -- it's recorded as-is instead
    of being raised, so it can't take down the retry/logging machinery whose
    whole purpose is to stop and show the human what happened.
    """
    try:
        return truncate(fetch())
    except CliError as exc:
        return {"error": str(exc)}


def run_task_logged_step(
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    step: Step,
    remaining_steps: list[Step],
    out_path: str,
    run_id: str,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[list[str], list[dict]]:
    """Runs one step via `step_runner.run_step`, retrying up to
    `MAX_STEP_ATTEMPTS` fresh attempts (Step6) before giving up, wrapped with
    before/after snapshot+screenshot capture and a `<out>.tasks.jsonl` entry
    (task_log.py). Kept outside `step_runner.run_step` itself so its
    turn-control loop stays untouched (plan/main/05-recording-and-resume.md
    decision table; plan/main/06-failure-handling.md).

    Before/after snapshot+screenshot are still captured exactly once each
    (before the first attempt, after the last) regardless of how many
    attempts run, so retrying doesn't add CLI calls beyond the attempts
    themselves. Every attempt's generated code is kept and concatenated in
    order into a single `<out>.tasks.jsonl` entry -- browser state is never
    rolled back between attempts, so an earlier attempt's code is still part
    of what actually happened to the session.

    `should_stop` (Step7), if given, is checked right after a failed attempt
    -- if it's now true, the remaining retry attempts are skipped instead of
    being spent. This step already ran (and failed), so it's not "untouched"
    the way a step run_steps() never got to is: the failure's `reason` stays
    whatever run_step actually reported (cli_error/blocked/etc.), and each
    note in step_failures gets a `"stopped": true` field instead of a
    `reason` override, so the real failure cause isn't lost.
    """
    recordings = task_log.recordings_dir(out_path)
    recordings.mkdir(parents=True, exist_ok=True)

    before_snapshot = _capture_or_placeholder(cli.snapshot_text, "snapshot")
    before_screenshot = _capture_or_placeholder(
        lambda: cli.screenshot(str(recordings / f"{step.id}-before.png")), "screenshot"
    )

    all_code: list[str] = []
    step_failures: list[dict] = []
    stopped_mid_retry = False
    attempt = 0
    for attempt in range(1, MAX_STEP_ATTEMPTS + 1):
        step_code, step_failures = run_step(
            cli, client, model, step, remaining_steps, out_path, run_id, attempt=attempt
        )
        all_code.extend(step_code)
        if not step_failures:
            break
        elif any(note.get("reason") == "disallowed_url" for note in step_failures):
            # Retrying after a disallowed navigation would just let the model
            # keep issuing tool calls against a host it's not allowed to
            # touch, which contradicts the "stop immediately" intent of the
            # URL allowlist -- burn no further attempts (plan/main/
            # 08-safety-guardrails.md decision table).
            break
        elif should_stop and should_stop():
            stopped_mid_retry = True
            break

    after_snapshot = _capture_or_placeholder(cli.snapshot_text, "snapshot")
    after_screenshot = _capture_or_placeholder(
        lambda: cli.screenshot(str(recordings / f"{step.id}-after.png")), "screenshot"
    )

    if step_failures:
        # All MAX_STEP_ATTEMPTS attempts failed (a successful attempt breaks
        # out of the loop above) -- fetch diagnostics once, only now.
        diagnostics = {
            "console": _capture_diagnostic(cli.console),
            "requests": _capture_diagnostic(cli.requests),
            "snapshot": truncate(after_snapshot),
            "screenshot_path": after_screenshot,
        }
        for note in step_failures:
            note["diagnostics"] = diagnostics
            note["hint"] = FAILURE_REASON_HINTS.get(note.get("reason"), "unknown reason")
            note["attempt"] = attempt
            note["max_attempts"] = MAX_STEP_ATTEMPTS
            note["stopped"] = stopped_mid_retry

    task_log.append_task_log(
        {
            "step_id": step.id,
            "instruction": step.instruction,
            "code": all_code,
            "attempts": attempt,
            "success": not step_failures,
            "before_snapshot": before_snapshot,
            "after_snapshot": after_snapshot,
            "before_screenshot": before_screenshot,
            "after_screenshot": after_screenshot,
        },
        out_path,
        run_id,
    )
    return all_code, step_failures


def run_steps(
    story_steps: list[Step],
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    out_path: str,
    run_id: str,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[list[StepBlock], list[dict]]:
    """Runs `story_steps` in order, stopping at the first step that produces
    failure_notes. Shared by run_vertical_slice/resume_vertical_slice here
    and orchestrator.run_story/resume_story, so all four entry points record
    and assemble tasks identically.

    `should_stop` (Step7), if given, is checked at the top of each iteration
    -- before that step is touched at all -- and is also passed through to
    `run_task_logged_step` for the finer-grained retry-boundary check. If it
    reports true here, the step is left entirely unattempted: a single
    `reason: "stopped"` failure_note is appended for it (no
    `run_task_logged_step` call, so no `<out>.tasks.jsonl` entry either) and
    the loop breaks, same shape as any other stop-at-first-failure step.
    """
    blocks: list[StepBlock] = []
    failure_notes: list[dict] = []
    for i, step in enumerate(story_steps):
        if should_stop and should_stop():
            failure_notes.append(
                {"step": step.id, "reason": "stopped", "hint": FAILURE_REASON_HINTS["stopped"]}
            )
            break
        logger.info("=== step %s: %s ===", step.id, step.instruction)
        step_code, step_failures = run_task_logged_step(
            cli, client, model, step, story_steps[i:], out_path, run_id, should_stop=should_stop
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
