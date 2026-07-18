"""Entry point: run one story end-to-end with no human mediation.

    python -m scripts.vertical_slice.main --story scripts/stories/search-demo.yaml

For each step: take a snapshot, then run a multi-turn tool-calling loop
(fresh context per step, no previous_response_id) -- ask the AI to act,
execute whatever tool calls it makes via playwright-cli, feed back each
call's result plus a fresh snapshot, and ask again. This repeats until the AI
calls finish_step (alone) or a per-step turn cap is hit, collecting the
generated Playwright TypeScript along the way. Stops the whole story early
and records a failure note if the AI reports itself blocked, never calls
finish_step within the turn cap, or a CLI call errors out.

Every turn (success or failure) is also appended to a `<out>.steps.jsonl`
file -- one JSON object per line with the step/turn number, the raw model
response output items, and every tool call's arguments/raw CLI output -- so
a stop reason can be read back afterwards instead of re-guessed from the
console log.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from . import config, prompts, tools
from .cli_executor import CliError, CliExecutor
from .story import Story, load_story

logger = logging.getLogger("vertical_slice")

# Safety cap on tool-calling turns within a single step, so a model that never
# calls finish_step can't loop forever. Not a retry mechanism (Step6 scope) --
# just a bound on one step's own back-and-forth.
MAX_TURNS_PER_STEP = 8


def write_spec_file(generated_code: list[str], out_path: str, test_name: str) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [line for code in generated_code for line in code.splitlines() if line.strip()]
    body = "\n".join(f"  {line}" for line in lines)
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


_SNAPSHOT_LOG_LIMIT = 2000


def _serialize_output_item(item) -> dict:
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


def _truncate(text: str, limit: int = _SNAPSHOT_LOG_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...<truncated, {len(text)} chars total>"


def step_log_path(out_path: str) -> Path:
    return Path(out_path).with_suffix(".steps.jsonl")


def append_step_log(entry: dict, out_path: str) -> None:
    """Append one full step record (prompt, raw model output, tool results) so
    the reason a step stopped can be read back later instead of re-guessed."""
    path = step_log_path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def run_playwright_test(spec_path: Path) -> bool:
    proc = subprocess.run(
        ["npx", "playwright", "test", str(spec_path)], capture_output=True, text=True
    )
    logger.info("npx playwright test output:\n%s", proc.stdout + proc.stderr)
    return proc.returncode == 0


def run_step(
    cli: CliExecutor,
    client: OpenAI,
    model: str,
    step,
    remaining_steps: list,
    out_path: str,
) -> tuple[list[str], list[dict]]:
    """Run one step as a multi-turn tool-calling loop.

    Calls the model, executes whatever tool(s) it asks for, feeds back each
    call's result plus a fresh snapshot, and asks again -- so the model sees
    what actually happened before deciding its next move, instead of having
    to plan the whole step blind in one shot. Repeats until the model calls
    finish_step (alone, done or blocked) or MAX_TURNS_PER_STEP is hit. Every
    turn is appended to the step log (see append_step_log).

    previous_response_id is intentionally never set: every *step* is a fresh
    context built from scratch (SPEC.md 2章). Turns within a step are chained
    by growing input_items locally instead, so that guarantee still holds
    across steps.
    """
    generated_code: list[str] = []
    failure_notes: list[dict] = []

    snapshot = cli.snapshot_text()
    input_items = prompts.build_input(remaining_steps=remaining_steps, current_step=step, snapshot=snapshot)

    for turn in range(1, MAX_TURNS_PER_STEP + 1):
        turn_snapshot = snapshot
        response = client.responses.create(
            model=model,
            input=input_items,
            tools=tools.TOOL_SCHEMAS,
            tool_choice="required",
        )
        input_items = input_items + list(response.output)

        output_items = [_serialize_output_item(item) for item in response.output]
        for item in output_items:
            if item.get("type") == "reasoning":
                # Normal for reasoning models; content itself is encrypted/opaque,
                # so just note it happened -- full record still goes to the step log.
                logger.info("step %s turn %s: model emitted a reasoning item (no readable text)", step.id, turn)
            elif item.get("type") != "function_call":
                # Unexpected under tool_choice="required" -- e.g. a text message or
                # refusal. Surface it in full instead of dropping it.
                logger.warning(
                    "step %s turn %s: non-call output item (%s): %s", step.id, turn, item.get("type"), item
                )

        calls = [item for item in response.output if item.type == "function_call"]
        finish_call = next((c for c in calls if c.name == "finish_step"), None)
        action_calls = [c for c in calls if c.name != "finish_step"]

        tool_results: list[dict] = []
        stop = False
        stop_reason: str | None = None

        if finish_call:
            args = json.loads(finish_call.arguments)
            logger.info("step %s finish_step (turn %s): %s", step.id, turn, args)
            tool_results.append({"name": finish_call.name, "arguments": args})
            stop = True
            stop_reason = "blocked" if args.get("status") == "blocked" else "done"
            if args.get("status") == "blocked":
                failure_notes.append({"step": step.id, "reason": "blocked", "note": args.get("note")})
            if action_calls:
                logger.warning(
                    "step %s turn %s: finish_step was called alongside %s other tool call(s); ignoring them",
                    step.id,
                    turn,
                    len(action_calls),
                )
        elif not action_calls:
            # Shouldn't happen under tool_choice="required", but guard anyway.
            logger.warning("step %s turn %s: no tool call in response, stopping", step.id, turn)
            failure_notes.append({"step": step.id, "reason": "no_tool_call", "turn": turn})
            stop = True
            stop_reason = "no_tool_call"
        else:
            for call in action_calls:
                args = json.loads(call.arguments)
                try:
                    result = tools.execute_tool(cli, call.name, args)
                except CliError as exc:
                    logger.error("step %s turn %s: %s(%s) failed: %s", step.id, turn, call.name, args, exc)
                    failure_notes.append(
                        {
                            "step": step.id,
                            "reason": "cli_error",
                            "tool": call.name,
                            "arguments": args,
                            "error": str(exc),
                        }
                    )
                    tool_results.append({"name": call.name, "arguments": args, "error": str(exc)})
                    input_items.append(
                        {"type": "function_call_output", "call_id": call.call_id, "output": f"error: {exc}"}
                    )
                    stop = True
                    stop_reason = "cli_error"
                    break

                tool_results.append(
                    {
                        "name": call.name,
                        "arguments": args,
                        "generated_code": result.generated_code,
                        "raw_output": _truncate(result.raw_output),
                    }
                )
                if result.generated_code:
                    generated_code.append(result.generated_code)
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": result.generated_code or "ok (no generated code)",
                    }
                )

            if not stop:
                snapshot = cli.snapshot_text()
                input_items.append(prompts.build_snapshot_followup(snapshot))

        append_step_log(
            {
                "step": step.id,
                "turn": turn,
                "instruction": step.instruction,
                # snapshot is logged (not the full `input`, which just wraps this
                # same text) so refs the model used can be cross-checked, capped
                # since accessibility-tree snapshots can run tens of KB.
                "snapshot": _truncate(turn_snapshot),
                "response_output": output_items,
                "usage": response.usage.model_dump() if response.usage else None,
                "tool_results": tool_results,
                "stopped": stop,
                "stop_reason": stop_reason,
            },
            out_path,
        )

        if stop:
            return generated_code, failure_notes

    logger.warning("step %s: finish_step not called within %s turns, stopping", step.id, MAX_TURNS_PER_STEP)
    failure_notes.append({"step": step.id, "reason": "max_turns_exceeded", "turns": MAX_TURNS_PER_STEP})
    return generated_code, failure_notes


def run_vertical_slice(story: Story, cli: CliExecutor, client: OpenAI, model: str, out_path: str) -> bool:
    generated_code: list[str] = []
    failure_notes: list[dict] = []
    step_log_path(out_path).unlink(missing_ok=True)

    open_result = cli.open(story.seed_url)
    if open_result.generated_code:
        generated_code.append(open_result.generated_code)

    for i, step in enumerate(story.steps):
        logger.info("=== step %s: %s ===", step.id, step.instruction)
        step_code, step_failures = run_step(cli, client, model, step, story.steps[i:], out_path)
        generated_code.extend(step_code)
        failure_notes.extend(step_failures)
        if step_failures:
            break
    else:
        logger.info("all steps completed")

    spec_path = write_spec_file(generated_code, out_path, story.name)
    write_failure_notes(failure_notes, out_path)

    if failure_notes:
        logger.warning("stopped early with failure notes; skipping npx playwright test")
        return False

    passed = run_playwright_test(spec_path)
    logger.info("npx playwright test %s", "passed" if passed else "failed")
    return passed


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", required=True, help="path to a story YAML file")
    parser.add_argument("--session", default="vertical-slice", help="playwright-cli session name")
    parser.add_argument("--model", default=None, help="overrides the AI_MODEL env var / default")
    parser.add_argument(
        "--out",
        default="tests/generated/search-demo.spec.ts",
        help="path to write the generated .spec.ts file",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    story = load_story(args.story)
    model = args.model or config.get_model()
    client = OpenAI(api_key=config.get_api_key(), base_url=config.get_base_url())
    cli = CliExecutor(session=args.session)

    try:
        passed = run_vertical_slice(story, cli, client, model, args.out)
    finally:
        cli.close()

    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
