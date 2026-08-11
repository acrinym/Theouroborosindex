from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _value(key: str, value: float) -> str:
    if key in {"product_share", "machinery_share", "far_from_value", "exact_coverage"}:
        return f"{value * 100:.1f}%"
    if key == "scaffolding_ratio":
        return f"{value:.2f}:1"
    if key == "recursive_depth":
        return str(int(value))
    return f"{value:.1f}"


def build_context_report_html(result: dict[str, Any]) -> str:
    cards = []
    for key, row in (result.get("dimensions") or {}).items():
        if not row.get("available"):
            cards.append(f"<article class=\"card\"><h3>{html.escape(str(row.get('label') or key))}</h3><p class=\"muted\">n/a — {html.escape(str(row.get('reason') or 'unavailable'))}</p></article>")
            continue
        cards.append(
            "<article class=\"card\">"
            f"<h3>{html.escape(str(row.get('label') or key))}</h3>"
            f"<div class=\"big\">{html.escape(_value(key, float(row['value'])))}</div>"
            f"<p>Percentile <strong>{float(row['percentile']):.1f}</strong> · {html.escape(str(row['band']))}</p>"
            f"<p class=\"muted\">Comparable n={int(row['cohort_size'])} · range {_value(key, float(row['minimum']))} → {_value(key, float(row['maximum']))}</p>"
            "</article>"
        )
    cohort = result.get("cohort") or {}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ouroboros Structural Context</title><style>
:root{{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0e1116;color:#e9edf2}}body{{margin:0;padding:32px}}main{{max-width:1120px;margin:auto}}.lead,.muted{{color:#aeb8c4;line-height:1.55}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:22px 0}}.card{{background:#151a21;border:1px solid #2a333e;border-radius:14px;padding:18px}}.big{{font-size:2rem;font-weight:700}}.notice{{border:1px solid #4f5b66;border-radius:12px;padding:14px 16px;margin:18px 0}}.pill{{display:inline-block;border:1px solid #394554;border-radius:999px;padding:5px 10px;margin:0 6px 6px 0}}
</style></head><body><main>
<h1>Ouroboros Structural Context</h1>
<p class="lead">Where this repository anatomy sits among comparable Index measurements. The corpus is deduplicated to one current record per repository before distributions are computed.</p>
<div><span class="pill">Comparable repositories: {int(cohort.get('repositories') or 0)}</span><span class="pill">Measurement: {html.escape(str(result.get('measurement_model') or 'unknown'))}</span><span class="pill">Canonical: {str(bool(cohort.get('canonical'))).lower()}</span></div>
<div class="notice"><strong>Not a leaderboard.</strong> Percentile means relative structural position only. Lower-tail and upper-tail measurements can both be deliberate, useful designs.</div>
<section class="grid">{''.join(cards)}</section>
<p class="muted">Bands: lower-tail &lt; 10th percentile, middle-range 10th–90th, upper-tail &gt; 90th. Missing evidence stays n/a rather than becoming zero or perfect.</p>
</main></body></html>"""


def write_context_report(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_context_report_html(result), encoding="utf-8")
    return destination.resolve()
