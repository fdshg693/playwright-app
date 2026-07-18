"""Output formatting for cost_summary.py: a per-step breakdown for a single
file, or a cross-run history table for multiple files.

See [[cost-summary]].
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scripts.internal.cost_aggregate import DEFAULT_PRICING_MODEL, PRICING_CSV_PATH


@dataclass
class RunCostRow:
    path: Path
    time: datetime
    time_is_fallback: bool
    model: str | None
    matched: bool
    overall: dict
    cost: float


def format_single_file_report(
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


def format_run_history_report(rows: list[RunCostRow]) -> str:
    """One line per run (oldest first) with its own model/cost, followed by
    the summed total. Step-level breakdown is intentionally omitted here --
    that's what format_single_file_report is for -- since printing every
    step of every run in a multi-run scan is unreadable."""
    if not rows:
        return "no matching .steps.jsonl files found"

    ordered = sorted(rows, key=lambda r: r.time)

    lines = ["run history (oldest first):", ""]
    total_cost = 0.0
    for row in ordered:
        total_cost += row.cost
        time_label = row.time.strftime("%Y-%m-%d %H:%M:%S")
        if row.time_is_fallback:
            time_label += " (mtime fallback)"
        model_label = row.model or "(unknown)"
        if not row.matched:
            model_label += f" (no pricing row, using '{DEFAULT_PRICING_MODEL}')"
        lines.append(
            f"  [{time_label}] {row.path} "
            f"model={model_label} "
            f"total_tokens={row.overall.get('total_tokens', 0)} "
            f"cost=${row.cost:.4f}"
        )

    lines.append("")
    lines.append(f"{len(ordered)} run(s), total estimated cost: ${total_cost:.4f}")

    return "\n".join(lines)
