"""Per-file token usage aggregation and price estimation for vertical_slice
`<out>.steps.jsonl` logs.

Moved out of cost_summary.py so the CLI entrypoint stays thin (see
[[cost-summary]]). Reads the `usage` (and `model`) field step_log.py's
append_step_log writes on every turn and sums input/output/cached/reasoning
tokens, both overall and per step. Per-token prices come from
`model_pricing.csv` in this same directory, keyed by model name; a model with
no matching row falls back to the `default` row in that file.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

PRICING_CSV_PATH = Path(__file__).parent / "model_pricing.csv"
DEFAULT_PRICING_MODEL = "default"


def load_usages(path: str) -> list[dict]:
    """Return one dict per turn that had a usage record: {step, turn, model, usage}.

    Lines that fail to parse as JSON are skipped with a warning on stderr
    instead of raising -- a run that crashed mid-turn can leave the last line
    of `.steps.jsonl` truncated, and that shouldn't take down aggregation
    across every other history file being scanned in the same invocation.
    """
    entries = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"warning: {path}:{lineno}: skipping malformed JSON line ({exc})", file=sys.stderr)
                continue
            usage = obj.get("usage")
            if usage is None:
                continue
            entries.append({"step": obj.get("step"), "turn": obj.get("turn"), "model": obj.get("model"), "usage": usage})
    return entries


def _extract(usage: dict) -> dict:
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "input_tokens": usage.get("input_tokens") or 0,
        "cached_tokens": input_details.get("cached_tokens") or 0,
        "cache_write_tokens": input_details.get("cache_write_tokens") or 0,
        "output_tokens": usage.get("output_tokens") or 0,
        "reasoning_tokens": output_details.get("reasoning_tokens") or 0,
        "total_tokens": usage.get("total_tokens") or 0,
    }


def aggregate(entries: list[dict]) -> tuple[dict, dict[int, dict]]:
    """Return (overall_totals, {step_id: step_totals})."""
    overall = defaultdict(int)
    per_step: dict[int, dict] = defaultdict(lambda: defaultdict(int))

    for entry in entries:
        fields = _extract(entry["usage"])
        for key, value in fields.items():
            overall[key] += value
            per_step[entry["step"]][key] += value

    return dict(overall), {step: dict(totals) for step, totals in per_step.items()}


def resolve_model(entries: list[dict], model_override: str | None) -> str | None:
    if model_override:
        return model_override
    models = {entry["model"] for entry in entries if entry.get("model")}
    if len(models) > 1:
        raise SystemExit(f"log contains multiple models {sorted(models)}; pass --model to pick one for pricing")
    return next(iter(models), None)


def load_pricing_table(csv_path: Path) -> dict[str, dict[str, float]]:
    if not csv_path.exists():
        raise SystemExit(f"pricing CSV not found: {csv_path}")

    table: dict[str, dict[str, float]] = {}
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            table[row["model"]] = {
                "input": float(row["input_price_per_1m"]),
                "output": float(row["output_price_per_1m"]),
                "cached_input": float(row["cached_input_price_per_1m"]),
            }

    if DEFAULT_PRICING_MODEL not in table:
        raise SystemExit(f"pricing CSV missing required '{DEFAULT_PRICING_MODEL}' row: {csv_path}")

    return table


def get_pricing(table: dict[str, dict[str, float]], model: str | None) -> tuple[dict[str, float], bool]:
    """Return (prices, matched) -- matched is False when falling back to the default row."""
    if model and model in table:
        return table[model], True
    return table[DEFAULT_PRICING_MODEL], False


def estimate_cost(totals: dict, prices: dict[str, float]) -> float:
    cached_tokens = totals.get("cached_tokens", 0)
    billable_input_tokens = totals.get("input_tokens", 0) - cached_tokens

    cost = (billable_input_tokens / 1_000_000) * prices["input"]
    cost += (cached_tokens / 1_000_000) * prices["cached_input"]
    cost += (totals.get("output_tokens", 0) / 1_000_000) * prices["output"]
    return cost
