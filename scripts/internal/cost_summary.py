"""CLI entrypoint for aggregating token usage / cost across vertical_slice
history logs (`{run_id}__{stem}.steps.jsonl`, see [[vertical-slice-runner]]).

    python -m scripts.internal.cost_summary tests/generated/search-demo.spec.steps.jsonl
    python -m scripts.internal.cost_summary tests/generated/search-demo.history/
    python -m scripts.internal.cost_summary tests/generated/ --start 2026-07-01 --end 2026-07-19T12:00:00
    python -m scripts.internal.cost_summary tests/generated/ --html cost_dashboard.html

A single file argument prints that run's step-by-step breakdown (the
original single-file behavior). Multiple files and/or directories print a
run-history table instead (one row per run, oldest first) plus a summed
total cost. Directories are scanned recursively for `*.steps.jsonl` only.
Passing `--html [PATH]` writes a self-contained HTML dashboard of the
run-history data instead of printing the text report (always run-history,
even for a single file -- see cost_html.py).

This module is wiring only: cost_log_discovery.py resolves paths/dirs and
applies the time range filter, cost_aggregate.py does the per-file
usage/pricing math, cost_report.py formats text output, cost_html.py formats
HTML output. See [[cost-summary]].
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from scripts.internal import cost_aggregate as aggregate
from scripts.internal import cost_html as html_report
from scripts.internal import cost_log_discovery as discovery
from scripts.internal import cost_report as report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "paths",
        nargs="+",
        help="`.steps.jsonl` file(s) and/or directories (scanned recursively) to aggregate",
    )
    parser.add_argument(
        "--start",
        default=None,
        type=datetime.fromisoformat,
        help="only include runs at/after this local time (ISO8601, e.g. 2026-07-01T00:00:00)",
    )
    parser.add_argument(
        "--end",
        default=None,
        type=datetime.fromisoformat,
        help="only include runs at/before this local time (ISO8601)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="override the model used for pricing lookup for files that can't resolve one on their own",
    )
    parser.add_argument(
        "--html",
        nargs="?",
        const="cost_dashboard.html",
        default=None,
        help=(
            "write a self-contained HTML dashboard of the run-history data to this path instead of "
            "printing a text report (always run-history, even for a single file). Omit the value to "
            "use the default path 'cost_dashboard.html'; omit the flag entirely to keep the existing "
            "text output"
        ),
    )
    args = parser.parse_args()

    single_file_mode = len(args.paths) == 1 and Path(args.paths[0]).is_file() and args.html is None

    files = discovery.discover_log_files(args.paths)
    files = discovery.filter_by_time_range(files, args.start, args.end)

    if not files:
        print("no matching .steps.jsonl files found (0 files after discovery/time filtering)")
        return

    pricing_table = aggregate.load_pricing_table(aggregate.PRICING_CSV_PATH)

    if single_file_mode:
        path = files[0]
        entries = aggregate.load_usages(str(path))
        if not entries:
            raise SystemExit(f"no usage records found in {path}")

        overall, per_step = aggregate.aggregate(entries)
        model = aggregate.resolve_model(entries, args.model)
        prices, matched = aggregate.get_pricing(pricing_table, model)
        cost = aggregate.estimate_cost(overall, prices)

        print(report.format_single_file_report(str(path), overall, per_step, model, matched, cost))
        return

    rows: list[report.RunCostRow] = []
    for path in files:
        entries = aggregate.load_usages(str(path))
        if not entries:
            print(f"warning: no usage records found in {path}, skipping", file=sys.stderr)
            continue

        overall, _per_step = aggregate.aggregate(entries)
        try:
            model = aggregate.resolve_model(entries, args.model)
        except SystemExit as exc:
            print(f"warning: {exc}, skipping {path}", file=sys.stderr)
            continue

        prices, matched = aggregate.get_pricing(pricing_table, model)
        cost = aggregate.estimate_cost(overall, prices)

        rows.append(
            report.RunCostRow(
                path=path,
                time=discovery.resolve_run_time(path),
                time_is_fallback=discovery.is_run_time_fallback(path),
                model=model,
                matched=matched,
                overall=overall,
                cost=cost,
            )
        )

    if args.html is not None:
        html_path = Path(args.html)
        html_path.write_text(html_report.render_html_report(rows), encoding="utf-8")
        total_cost = sum(row.cost for row in rows)
        print(f"wrote {len(rows)} run(s) to {html_path} (total estimated cost: ${total_cost:.4f})")
        return

    print(report.format_run_history_report(rows))


if __name__ == "__main__":
    main()
