from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .neighbors import CATEGORY_ORDER


_CATEGORY_LABELS = {
    "core-product": "Core product",
    "user-surface": "User surface",
    "essential-support": "Essential support",
    "developer-tooling": "Developer tooling",
    "testing": "Testing",
    "observability": "Observability",
    "verification": "Verification",
    "audit-provenance": "Audit / provenance",
    "process-machinery": "Process machinery",
    "meta-machinery": "Meta-machinery",
    "documentation": "Documentation",
    "unknown": "Unknown",
}


def _h(value: object) -> str:
    return escape(str(value), quote=True)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _fingerprint_bar(fingerprint: dict[str, Any]) -> str:
    shares = fingerprint.get("code_category_shares") or {}
    segments = []
    for category in CATEGORY_ORDER:
        share = float(shares.get(category, 0.0) or 0.0)
        if share <= 0:
            continue
        segments.append(
            f'<span class="seg cat-{_h(category)}" style="width:{share*100:.5f}%" '
            f'title="{_h(_CATEGORY_LABELS.get(category, category))}: {share*100:.1f}%"></span>'
        )
    return '<div class="fingerprint-bar">' + "".join(segments) + "</div>"


def _category_rows(match: dict[str, Any]) -> str:
    rows = []
    for row in match.get("category_differences", []):
        rows.append(
            "<tr>"
            f"<td>{_h(_CATEGORY_LABELS.get(row['category'], row['category']))}</td>"
            f"<td>{_pct(float(row['query']))}</td>"
            f"<td>{_pct(float(row['candidate']))}</td>"
            f"<td>{float(row['delta'])*100:+.1f} pp</td>"
            "</tr>"
        )
    return "".join(rows)


def _component_rows(match: dict[str, Any]) -> str:
    labels = {
        "code_composition": "Code composition",
        "symbol_composition": "Symbol composition",
        "recursive_depth": "Recursive depth",
        "semantic_index": "Semantic Index",
        "far_from_value": "Far from value",
        "exact_coverage": "Exact coverage",
    }
    rows = []
    for key, component in match.get("components", {}).items():
        rows.append(
            "<tr>"
            f"<td>{_h(labels.get(key, key))}</td>"
            f"<td>{float(component['distance']):.3f}</td>"
            f"<td>{float(component['effective_weight'])*100:.1f}%</td>"
            f"<td>{float(component['contribution']):.4f}</td>"
            "</tr>"
        )
    return "".join(rows)


def build_neighbors_report_html(result: dict[str, Any]) -> str:
    query = result["query"]
    neighbors = result.get("neighbors", [])
    cohort = result.get("cohort", {})
    cards = []
    for rank, match in enumerate(neighbors, 1):
        fingerprint = match["fingerprint"]
        warnings = ""
        if not match.get("comparable_measurement_model"):
            warnings = '<p class="warning">Measurement model/settings differ from the query; read this match cautiously.</p>'
        explanation = "".join(f"<li>{_h(line)}</li>" for line in match.get("explanation", []))
        cards.append(
            f"""
<details class="neighbor-card" {"open" if rank == 1 else ""}>
  <summary>
    <span class="rank">#{rank}</span>
    <span class="repo"><strong>{_h(match['repository_name'])}</strong><small>{_h(match.get('repository_sha') or 'SHA unavailable')}</small></span>
    <span class="distance"><strong>{float(match['distance']):.3f}</strong><small>structural distance</small></span>
  </summary>
  <div class="neighbor-body">
    {warnings}
    {_fingerprint_bar(fingerprint)}
    <div class="mini-metrics">
      <span>Product <strong>{_pct(fingerprint.get('direct_product_share'))}</strong></span>
      <span>Machinery <strong>{_pct(fingerprint.get('machinery_share'))}</strong></span>
      <span>Depth <strong>{int(fingerprint.get('recursive_depth') or 0)}</strong></span>
      <span>Semantic Index <strong>{float(fingerprint.get('semantic_index') or 0):.1f}</strong></span>
      <span>Exact coverage <strong>{_pct(fingerprint.get('exact_coverage'))}</strong></span>
    </div>
    <ul>{explanation}</ul>
    <div class="grid-2">
      <div>
        <h3>Largest code-purpose differences</h3>
        <div class="table-wrap"><table><thead><tr><th>Category</th><th>Query</th><th>Neighbor</th><th>Delta</th></tr></thead><tbody>{_category_rows(match)}</tbody></table></div>
      </div>
      <div>
        <h3>Distance decomposition</h3>
        <div class="table-wrap"><table><thead><tr><th>Dimension</th><th>Distance</th><th>Weight</th><th>Contribution</th></tr></thead><tbody>{_component_rows(match)}</tbody></table></div>
      </div>
    </div>
  </div>
</details>
"""
        )
    if not cards:
        cards.append('<div class="empty">No eligible structural neighbors were found in this corpus under the current comparison rules.</div>')

    excluded = cohort.get("excluded") or {}
    excluded_text = ", ".join(f"{_h(key.replace('_', ' '))}: {value}" for key, value in excluded.items()) or "none"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ouroboros Structural Neighborhood — {_h(query.get('repository_name'))}</title>
<style>
:root {{ color-scheme: dark; --bg:#0d1117; --panel:#151b23; --panel2:#1b2330; --line:#303a46; --text:#eef2f6; --muted:#9da9b6; --accent:#78d6b2; --warn:#f3c76b; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:radial-gradient(circle at top right,#172132 0,var(--bg) 34rem); color:var(--text); font:15px/1.5 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ width:min(1180px,calc(100% - 30px)); margin:0 auto; padding:32px 0 64px; }}
header {{ margin-bottom:22px; }}
h1,h2,h3 {{ line-height:1.15; }}
h1 {{ margin:0; font-size:clamp(28px,5vw,43px); }}
h2 {{ margin:0 0 10px; }}
h3 {{ font-size:15px; }}
.subtitle,.muted,small {{ color:var(--muted); }}
.panel,.neighbor-card {{ border:1px solid var(--line); background:var(--panel); border-radius:16px; box-shadow:0 10px 28px #0003; }}
.panel {{ padding:18px; margin:16px 0; }}
.query-grid {{ display:grid; grid-template-columns:minmax(0,2fr) repeat(4,minmax(110px,1fr)); gap:10px; align-items:stretch; }}
.metric {{ border:1px solid var(--line); border-radius:12px; padding:12px; background:var(--panel2); }}
.metric strong {{ display:block; font-size:23px; margin-top:4px; }}
.fingerprint-bar {{ display:flex; width:100%; min-height:22px; overflow:hidden; border-radius:999px; border:1px solid var(--line); background:#080c11; margin:10px 0; }}
.seg {{ min-width:2px; }}
.cat-core-product {{ background:#2f8f72; }} .cat-user-surface {{ background:#57b894; }} .cat-essential-support {{ background:#4f7fab; }}
.cat-testing {{ background:#a987db; }} .cat-developer-tooling {{ background:#d59a55; }} .cat-observability {{ background:#d0709c; }}
.cat-verification {{ background:#c9ad54; }} .cat-audit-provenance {{ background:#d26969; }} .cat-process-machinery {{ background:#b85f7b; }}
.cat-meta-machinery {{ background:#a54f4f; }} .cat-documentation {{ background:#6f7b87; }} .cat-unknown {{ background:#4a5058; }}
.neighbor-card {{ margin:11px 0; overflow:hidden; }}
.neighbor-card summary {{ cursor:pointer; display:grid; grid-template-columns:58px 1fr auto; gap:12px; align-items:center; padding:14px 16px; list-style:none; }}
.neighbor-card summary::-webkit-details-marker {{ display:none; }}
.rank {{ color:var(--accent); font-size:20px; font-weight:800; }} .repo small,.distance small {{ display:block; }}
.distance {{ text-align:right; }} .distance strong {{ font-size:24px; }}
.neighbor-body {{ border-top:1px solid var(--line); padding:14px 16px 18px; }}
.mini-metrics {{ display:flex; gap:16px; flex-wrap:wrap; color:var(--muted); }} .mini-metrics strong {{ color:var(--text); }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; }} th,td {{ text-align:left; border-bottom:1px solid var(--line); padding:7px 8px; white-space:nowrap; }} th {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.05em; }}
.warning {{ border:1px solid #f3c76b66; background:#f3c76b11; padding:9px 11px; border-radius:9px; }}
.empty {{ padding:22px; border:1px dashed var(--line); border-radius:12px; color:var(--muted); }}
.note {{ border-left:4px solid var(--accent); padding-left:14px; }}
@media(max-width:850px) {{ .query-grid,.grid-2 {{ grid-template-columns:1fr; }} .neighbor-card summary {{ grid-template-columns:45px 1fr; }} .distance {{ grid-column:2; text-align:left; }} }}
</style>
</head>
<body>
<main>
<header>
  <h1>Structural Neighborhood</h1>
  <div class="subtitle">Ouroboros anatomy neighbors for <strong>{_h(query.get('repository_name'))}</strong></div>
</header>
<section class="panel note">
  <strong>Nearest means structurally similar, not better.</strong>
  <div class="muted">Distance is a bounded comparison of code-purpose composition, symbol-role composition, recursive depth, Semantic Index, far-from-value share, and exact relationship coverage when available.</div>
</section>
<section class="panel">
  <h2>Query fingerprint</h2>
  {_fingerprint_bar(query)}
  <div class="query-grid">
    <div class="metric"><small>Repository SHA</small><strong style="font-size:14px;overflow-wrap:anywhere">{_h(query.get('repository_sha') or 'unavailable')}</strong></div>
    <div class="metric"><small>Product</small><strong>{_pct(query.get('direct_product_share'))}</strong></div>
    <div class="metric"><small>Machinery</small><strong>{_pct(query.get('machinery_share'))}</strong></div>
    <div class="metric"><small>Depth</small><strong>{int(query.get('recursive_depth') or 0)}</strong></div>
    <div class="metric"><small>Semantic Index</small><strong>{float(query.get('semantic_index') or 0):.1f}</strong></div>
  </div>
</section>
<section class="panel">
  <h2>Corpus cohort</h2>
  <div class="mini-metrics"><span>Records seen <strong>{int(cohort.get('records_seen') or 0)}</strong></span><span>Eligible <strong>{int(cohort.get('eligible') or 0)}</strong></span><span>Returned <strong>{int(cohort.get('returned') or 0)}</strong></span></div>
  <p class="muted">Excluded: {excluded_text}. Cross-model comparison: {"enabled" if cohort.get('cross_model_enabled') else "disabled"}.</p>
</section>
<section>
  <h2>Nearest repository anatomy</h2>
  {''.join(cards)}
</section>
</main>
</body>
</html>
"""


def write_neighbors_report(result: dict[str, Any], target: str | Path) -> Path:
    destination = Path(target).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_neighbors_report_html(result), encoding="utf-8")
    return destination.resolve()
