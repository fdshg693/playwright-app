"""Aggregate token usage / cost from a vertical_slice `<out>.steps.jsonl` log.

    python -m scripts.internal.cost_summary tests/generated/search-demo.spec.steps.jsonl

Reads the `usage` (and `model`) field step_log.py's append_step_log writes on
every turn (see [[vertical-slice-runner]]) and sums input/output/cached/reasoning
tokens, both overall and per step. Per-token prices come from
`model_pricing.csv` in this same directory, keyed by model name; a model with
no matching row falls back to the `default` row in that file.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

PRICING_CSV_PATH = Path(__file__).parent / "model_pricing.csv"
DEFAULT_PRICING_MODEL = "default"


def load_usages(path: str) -> list[dict]:
    """Return one dict per turn that had a usage record: {step, turn, model, usage}."""
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            usage = obj.get("usage")
            if usage is None:
                continue
            entries.append({"step": obj.get("step"), "turn": obj.get("turn"), "model": obj.get("model"), "usage": usage})
    return entries


def _extract(usage: dict) -> dict:
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "cached_tokens": input_details.get("cached_tokens", 0),
        "cache_write_tokens": input_details.get("cache_write_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "reasoning_tokens": output_details.get("reasoning_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
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


def format_report(
    path: str,
    overall: dict,
    per_step: dict[int, dict],
    model: str | None,
    matched: bool,
    cost: float,
) -> str:
    lines = [f"usage summary: {path}", ""]

    lines.append("per step:")
    for step in sorted(per_step):
        t = per_step[step]
        lines.append(
            f"  step {step}: input={t.get('input_tokens', 0)} "
            f"(cached={t.get('cached_tokens', 0)}, cache_write={t.get('cache_write_tokens', 0)}) "
            f"output={t.get('output_tokens', 0)} (reasoning={t.get('reasoning_tokens', 0)}) "
            f"total={t.get('total_tokens', 0)}"
        )

    lines.append("")
    lines.append(
        f"overall: input={overall.get('input_tokens', 0)} "
        f"(cached={overall.get('cached_tokens', 0)}, cache_write={overall.get('cache_write_tokens', 0)}) "
        f"output={overall.get('output_tokens', 0)} (reasoning={overall.get('reasoning_tokens', 0)}) "
        f"total={overall.get('total_tokens', 0)}"
    )

    lines.append("")
    model_label = model or "(unknown)"
    if matched:
        lines.append(f"pricing: model={model_label} (matched row in {PRICING_CSV_PATH.name})")
    else:
        lines.append(
            f"pricing: model={model_label} (no row in {PRICING_CSV_PATH.name}, using '{DEFAULT_PRICING_MODEL}' row)"
        )
    lines.append(f"estimated cost: ${cost:.4f}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("steps_jsonl", help="path to a <out>.steps.jsonl file")
    parser.add_argument(
        "--model",
        default=None,
        help="override the model used for pricing lookup (log entries may predate the 'model' field)",
    )
    args = parser.parse_args()

    path = Path(args.steps_jsonl)
    if not path.exists():
        raise SystemExit(f"not found: {path}")

    entries = load_usages(str(path))
    if not entries:
        raise SystemExit(f"no usage records found in {path}")

    overall, per_step = aggregate(entries)
    model = resolve_model(entries, args.model)

    pricing_table = load_pricing_table(PRICING_CSV_PATH)
    prices, matched = get_pricing(pricing_table, model)
    cost = estimate_cost(overall, prices)

    print(format_report(str(path), overall, per_step, model, matched, cost))


if __name__ == "__main__":
    main()
