"""Runs one story step as a multi-turn tool-calling loop.

Fresh context per step, no previous_response_id (SPEC.md 2章): calls the
model, executes whatever tool call(s) it asks for via playwright-cli, feeds
back each call's result plus a fresh snapshot, and asks again. Repeats until
the model calls finish_step (alone) or MAX_TURNS_PER_STEP is hit.
"""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from . import prompts, tools
from .cli_executor import CliError, CliExecutor
from .step_log import append_step_log, serialize_output_item, truncate

logger = logging.getLogger("vertical_slice")

# Safety cap on tool-calling turns within a single step, so a model that never
# calls finish_step can't loop forever. Not a retry mechanism (Step6 scope) --
# just a bound on one step's own back-and-forth.
MAX_TURNS_PER_STEP = 8


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
    turn is appended to the step log (see step_log.append_step_log).

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

        output_items = [serialize_output_item(item) for item in response.output]
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
                        "raw_output": truncate(result.raw_output),
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
                "snapshot": truncate(turn_snapshot),
                "response_output": output_items,
                # response.model is what actually served the request (an
                # alias/env override in `model` may resolve to something
                # else); requested_model keeps the original string around so
                # the two can be compared later (cost_summary.py prices off
                # "model").
                "model": response.model,
                "requested_model": model,
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
