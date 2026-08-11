from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _ratio(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.2f}:1"


def _short(value: Any) -> str:
    return "unknown" if not value else str(value)[:10]


def build_story_report_html(story: dict[str, Any]) -> str:
    current = story.get("current") or {}
    history = story.get("history") or {}
    drivers_artifact = story.get("drivers") or {}
    drivers = drivers_artifact.get("drivers") or {}
    context = story.get("context") or {}
    warnings = (story.get("coherence") or {}).get("warnings") or []

    event_items = []
    for event in history.get("events") or []:
        kind = str(event.get("type") or "structural-change")
        label = kind.replace("-", " ").title()
        detail = ""
        if kind == "directory-crossover":
            detail = str(event.get("path") or "")
        elif kind == "recursive-depth-change":
            detail = f"{event.get('before')} → {event.get('after')}"
        elif kind == "repository-dominance-shift":
            detail = f"{event.get('from')} → {event.get('to')}"
        event_items.append(
            f"<li><code>{html.escape(_short(event.get('commit')))}</code> <strong>{html.escape(label)}</strong> {html.escape(detail)} <span class=\"muted\">{html.escape(str(event.get('subject') or ''))}</span></li>"
        )

    driver_rows = []
    for row in drivers.get("files") or []:
        driver_rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(row.get('path') or ''))}</code></td>"
            f"<td>{html.escape(str(row.get('status') or ''))}</td>"
            f"<td>{html.escape(str(row.get('before_category') or '—'))} → {html.escape(str(row.get('after_category') or '—'))}</td>"
            f"<td>{int(row.get('delta_code_lines') or 0):+,}</td>"
            "</tr>"
        )

    context_cards = []
    for key, row in (context.get("dimensions") or {}).items():
        if row.get("available"):
            context_cards.append(
                f"<article class=\"mini\"><h3>{html.escape(str(row.get('label') or key))}</h3><div class=\"big\">{float(row.get('percentile') or 0):.1f}th</div><p class=\"muted\">{html.escape(str(row.get('band') or ''))} · n={int(row.get('cohort_size') or 0)}</p></article>"
            )

    warning_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings)
    sources = story.get("sources") or {}
    source_pills = "".join(
        f"<span class=\"pill\">{html.escape(name.replace('_', ' '))}: {'yes' if enabled else 'no'}</span>"
        for name, enabled in sources.items()
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ouroboros Anatomy Story</title><style>
:root{{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0e1116;color:#e9edf2}}body{{margin:0;padding:32px}}main{{max-width:1180px;margin:auto}}h1,h2,h3{{margin-top:0}}.lead,.muted{{color:#aeb8c4;line-height:1.55}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}.card,.mini,.panel{{background:#151a21;border:1px solid #2a333e;border-radius:14px;padding:18px}}.panel{{margin:20px 0;overflow:auto}}.big{{font-size:1.75rem;font-weight:700}}.pill{{display:inline-block;border:1px solid #394554;border-radius:999px;padding:5px 10px;margin:0 6px 6px 0}}table{{border-collapse:collapse;width:100%;min-width:720px}}th,td{{border-bottom:1px solid #28313b;padding:9px 11px;text-align:left}}th{{color:#aeb8c4}}code{{color:#c8e2d7}}.warning{{border:1px solid #6a5b3d;background:#201d17;border-radius:12px;padding:14px 16px}}
</style></head><body><main>
<h1>Ouroboros Anatomy Story</h1>
<p class="lead">One deterministic view of current anatomy, its recent structural evolution, the evidence behind a selected change, and corpus context. No new score or AI-written verdict is introduced here.</p>
<div>{source_pills}</div>
<section class="grid">
<article class="card"><h3>Product</h3><div class="big">{_pct(current.get('product_share'))}</div></article>
<article class="card"><h3>Machinery</h3><div class="big">{_pct(current.get('machinery_share'))}</div></article>
<article class="card"><h3>Scaffold / product</h3><div class="big">{_ratio(current.get('scaffolding_ratio'))}</div></article>
<article class="card"><h3>Exact depth</h3><div class="big">{int(current.get('recursive_depth') or 0)}</div></article>
<article class="card"><h3>Semantic Index</h3><div class="big">{float(current.get('semantic_index') or 0):.1f}</div></article>
<article class="card"><h3>Exact coverage</h3><div class="big">{_pct(current.get('exact_coverage'))}</div></article>
</section>
<section class="panel"><h2>When did the structure move?</h2><ul>{''.join(event_items) or '<li>No bounded-history artifact supplied, or no tracked events in its range.</li>'}</ul></section>
<section class="panel"><h2>What moved around the selected change?</h2><p class="muted">Largest observed adjacent structural contributors; evidence, not blame.</p><table><thead><tr><th>File</th><th>Status</th><th>Role movement</th><th>Δ LOC</th></tr></thead><tbody>{''.join(driver_rows) or '<tr><td colspan="4">No Change Drivers artifact supplied.</td></tr>'}</tbody></table></section>
<section><h2>Is this anatomy unusual?</h2><div class="grid">{''.join(context_cards) or '<article class="mini"><p>No Structural Context artifact supplied.</p></article>'}</div><p class="muted">Percentiles are relative structural position, not quality rank.</p></section>
{f'<section class="warning"><h2>Artifact coherence notes</h2><ul>{warning_html}</ul></section>' if warning_html else ''}
<section class="panel"><h2>Trust boundary</h2><p>All analysis remains static. Target repository code is treated as data. This story composes existing Ouroboros artifacts; it does not execute target code, crawl repositories, produce a policy gate, or infer developer blame.</p><p class="muted">Current commit: <code>{html.escape(_short(current.get('sha')))}</code></p></section>
</main></body></html>"""


def write_story_report(story: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_story_report_html(story), encoding="utf-8")
    return destination.resolve()
