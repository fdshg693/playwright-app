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

from .cli_executor import CliExecutor
from .step_log import step_log_path
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


def run_vertical_slice(story: Story, cli: CliExecutor, client: OpenAI, model: str, out_path: str) -> bool:
    blocks: list[StepBlock] = []
    failure_notes: list[dict] = []
    step_log_path(out_path).unlink(missing_ok=True)

    open_result = cli.open(story.seed_url)
    if open_result.generated_code:
        blocks.append(StepBlock(step=None, code=[open_result.generated_code]))

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
        return False

    passed = run_playwright_test(spec_path)
    logger.info("npx playwright test %s", "passed" if passed else "failed")
    return passed
