from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{float(value):.2f}:1"


def _short(sha: str | None) -> str:
    return "unknown" if not sha else sha[:10]


def _event_text(event: dict[str, Any]) -> str:
    kind = event.get("type")
    if kind == "repository-dominance-shift":
        return f"Repository balance shifted from {event.get('from')} to {event.get('to')}."
    if kind == "directory-crossover":
        return f"{event.get('path')} crossed from product-dominant to machinery-dominant."
    if kind == "recursive-depth-change":
        return f"Max exact recursive depth changed from {event.get('before')} to {event.get('after')}."
    return str(kind or "structural change")


def build_history_report_html(result: dict[str, Any]) -> str:
    range_info = result.get("range") or {}
    checkpoints = result.get("checkpoints") or []
    events = result.get("events") or []
    event_commits = {str(event.get("commit")) for event in events}

    rows = []
    for checkpoint in checkpoints:
        sha = str(checkpoint.get("sha") or "")
        marker = " class=\"event-row\"" if sha in event_commits else ""
        rows.append(
            "<tr" + marker + ">"
            f"<td><code>{html.escape(_short(sha))}</code></td>"
            f"<td>{html.escape(str(checkpoint.get('authored_at') or ''))}</td>"
            f"<td>{html.escape(str(checkpoint.get('subject') or ''))}</td>"
            f"<td>{_pct(float(checkpoint.get('product_share') or 0.0))}</td>"
            f"<td>{_pct(float(checkpoint.get('machinery_share') or 0.0))}</td>"
            f"<td>{_ratio(checkpoint.get('scaffolding_ratio'))}</td>"
            f"<td>{int(checkpoint.get('recursive_depth') or 0)}</td>"
            f"<td>{float(checkpoint.get('semantic_index') or 0.0):.1f}</td>"
            f"<td>{_pct(checkpoint.get('exact_coverage'))}</td>"
            "</tr>"
        )

    event_cards = []
    for event in events:
        extra = ""
        if event.get("type") == "directory-crossover":
            before = event.get("before") or {}
            after = event.get("after") or {}
            extra = (
                "<div class=\"evidence\">"
                f"Before: product {int(before.get('product_lines') or 0):,} LOC · machinery {int(before.get('machinery_lines') or 0):,} LOC<br>"
                f"After: product {int(after.get('product_lines') or 0):,} LOC · machinery {int(after.get('machinery_lines') or 0):,} LOC"
                "</div>"
            )
        elif event.get("type") == "repository-dominance-shift":
            product = event.get("product_share") or {}
            machinery = event.get("machinery_share") or {}
            extra = (
                "<div class=\"evidence\">"
                f"Product: {_pct(product.get('before'))} → {_pct(product.get('after'))}<br>"
                f"Machinery: {_pct(machinery.get('before'))} → {_pct(machinery.get('after'))}"
                "</div>"
            )
        event_cards.append(
            "<article class=\"event\">"
            f"<div class=\"event-meta\"><code>{html.escape(_short(str(event.get('commit') or '')))}</code> · {html.escape(str(event.get('authored_at') or ''))}</div>"
            f"<h3>{html.escape(_event_text(event))}</h3>"
            f"<p>{html.escape(str(event.get('subject') or ''))}</p>"
            f"{extra}"
            "</article>"
        )

    if not event_cards:
        event_cards.append(
            "<div class=\"empty\">No repository-dominance, directory-crossover, or recursive-depth events occurred in this bounded range.</div>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ouroboros Bounded History</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:#0e1116; color:#e9edf2; }}
body {{ margin:0; padding:32px; }}
main {{ max-width:1200px; margin:0 auto; }}
h1,h2,h3 {{ margin-top:0; }}
.lead {{ color:#aeb8c4; max-width:900px; line-height:1.55; }}
.pill {{ display:inline-block; border:1px solid #394554; border-radius:999px; padding:5px 10px; margin:0 6px 6px 0; color:#c7d0db; }}
.panel {{ background:#151a21; border:1px solid #2a333e; border-radius:14px; padding:20px; margin:20px 0; overflow:auto; }}
table {{ border-collapse:collapse; width:100%; min-width:900px; }}
th,td {{ border-bottom:1px solid #28313b; padding:10px 12px; text-align:left; vertical-align:top; }}
th {{ color:#aeb8c4; font-size:.85rem; }}
.event-row {{ background:#1b2522; }}
.event {{ border-left:4px solid #7ab59d; background:#151a21; padding:16px 18px; margin:12px 0; border-radius:0 12px 12px 0; }}
.event-meta,.evidence,.empty {{ color:#aeb8c4; }}
code {{ color:#c8e2d7; }}
.notice {{ border:1px solid #4f5b66; border-radius:12px; padding:14px 16px; color:#cbd3dc; }}
</style>
</head>
<body>
<main>
<h1>Ouroboros Bounded History</h1>
<p class="lead">A canonical static scan of every first-parent commit in an explicit bounded range. Historical snapshots are read with <code>git archive</code>; target repository code is never executed.</p>
<div>
<span class="pill">Repository: {html.escape(str(result.get('repository') or ''))}</span>
<span class="pill">From: {_short(range_info.get('from_sha'))}</span>
<span class="pill">To: {_short(range_info.get('to_sha'))}</span>
<span class="pill">Commits scanned: {int(range_info.get('commits_scanned') or 0)}</span>
<span class="pill">Sampled: no</span>
</div>
<div class="notice">This report is exact only for the stated <strong>first-parent range</strong>. Merge-side histories are intentionally not traversed, and ranges larger than the configured bound are refused rather than sampled.</div>
<section class="panel">
<h2>History timeline</h2>
<table>
<thead><tr><th>Commit</th><th>Authored</th><th>Subject</th><th>Product</th><th>Machinery</th><th>Scaffold/Product</th><th>Exact depth</th><th>Semantic Index</th><th>Exact coverage</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
</section>
<section>
<h2>Structural change points</h2>
{''.join(event_cards)}
</section>
</main>
</body>
</html>
"""


def write_history_report(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_history_report_html(result), encoding="utf-8")
    return destination.resolve()
