"""Self-contained static HTML dashboard for cost_summary.py's run-history
rows.

Renders the same `RunCostRow` list that `cost_report.format_run_history_report`
turns into a text table, but as a standalone HTML page: a header (run count /
time range / total cost), a run-history table, and a minimal inline-SVG bar
chart of per-run cost. No aggregation/pricing logic lives here -- rows are
taken as-is from cost_aggregate.py/cost_report.py's existing output. No
external JS/CSS libraries or CDN references are used, so the returned string
can be written to a file and opened directly (`file://`) or shared as a
single file. See [[cost-summary]].
"""

from __future__ import annotations

import html

from scripts.internal import cost_report as report
from scripts.internal.cost_aggregate import DEFAULT_PRICING_MODEL


def _render_bar_chart(rows: list[report.RunCostRow]) -> str:
    """One <rect> per row (oldest first, same order as the table), height
    proportional to that run's cost relative to the most expensive run in
    `rows`. Purely decorative/inline SVG -- no JS, no external assets."""
    if not rows:
        return ""

    bar_width = 40
    gap = 12
    chart_height = 160
    plot_height = chart_height - 20  # leave headroom so the tallest bar isn't clipped
    max_cost = max((row.cost for row in rows), default=0.0)
    width = len(rows) * (bar_width + gap) + gap

    bars = []
    for i, row in enumerate(rows):
        bar_height = 0.0 if max_cost <= 0 else (row.cost / max_cost) * plot_height
        x = gap + i * (bar_width + gap)
        y = chart_height - bar_height
        label = html.escape(f"{row.time.strftime('%Y-%m-%d %H:%M:%S')}: ${row.cost:.4f}")
        bars.append(
            f'<rect class="bar" x="{x}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}">'
            f"<title>{label}</title></rect>"
        )

    return (
        f'<svg viewBox="0 0 {width} {chart_height}" width="{width}" height="{chart_height}" '
        f'role="img" aria-label="estimated cost per run, oldest first">'
        + "".join(bars)
        + "</svg>"
    )


def _render_table_rows(rows: list[report.RunCostRow]) -> str:
    lines = []
    for row in rows:
        time_label = row.time.strftime("%Y-%m-%d %H:%M:%S")
        if row.time_is_fallback:
            time_label += " (mtime fallback)"
        model_label = row.model or "(unknown)"
        if not row.matched:
            model_label += f" (no pricing row, using '{DEFAULT_PRICING_MODEL}')"
        lines.append(
            "<tr>"
            f"<td>{html.escape(time_label)}</td>"
            f"<td>{html.escape(str(row.path))}</td>"
            f"<td>{html.escape(model_label)}</td>"
            f"<td>{row.overall.get('total_tokens', 0)}</td>"
            f"<td>${row.cost:.4f}</td>"
            "</tr>"
        )
    return "\n      ".join(lines)


def _wrap_page(body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>cost dashboard</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
          margin: 2rem; color: #1a1a1a; background: #fff; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 0.25rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; font-size: 0.9rem; }}
  th {{ background: #f5f5f5; }}
  svg {{ background: #fafafa; border: 1px solid #ddd; }}
  rect.bar {{ fill: #4a7fd4; }}
  rect.bar:hover {{ fill: #2f5aa8; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def render_html_report(rows: list[report.RunCostRow]) -> str:
    """Build a self-contained HTML page from the same rows
    format_run_history_report formats as text: a header, a run-history
    table, and a bar chart of per-run cost. Rows are sorted oldest-first,
    same as the text report. All rows-derived strings (paths, model names)
    are HTML-escaped before being embedded."""
    if not rows:
        return _wrap_page("<h1>cost dashboard</h1><p>no matching .steps.jsonl files found</p>")

    ordered = sorted(rows, key=lambda r: r.time)
    total_cost = sum(row.cost for row in ordered)
    start_label = html.escape(ordered[0].time.strftime("%Y-%m-%d %H:%M:%S"))
    end_label = html.escape(ordered[-1].time.strftime("%Y-%m-%d %H:%M:%S"))

    body = f"""<h1>cost dashboard</h1>
  <p>{len(ordered)} run(s) &middot; {start_label} &ndash; {end_label} &middot; total estimated cost: ${total_cost:.4f}</p>

  <h2>cost per run</h2>
  {_render_bar_chart(ordered)}

  <h2>run history</h2>
  <table>
    <thead>
      <tr><th>time</th><th>path</th><th>model</th><th>total tokens</th><th>cost</th></tr>
    </thead>
    <tbody>
      {_render_table_rows(ordered)}
    </tbody>
  </table>
"""
    return _wrap_page(body)
