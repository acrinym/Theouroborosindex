from __future__ import annotations

from html import escape
from pathlib import Path

from . import __version__


def _h(value: object) -> str:
    return escape(str(value), quote=True)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.1f} pp"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}:1"


def _ratio_delta(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}"


def _metric_card(label: str, metric: dict, formatter, delta_formatter) -> str:
    return f"""
    <div class="card">
      <div class="label">{_h(label)}</div>
      <div class="value">{_h(formatter(metric.get('before')))} → {_h(formatter(metric.get('after')))}</div>
      <div class="delta">{_h(delta_formatter(metric.get('delta')))}</div>
    </div>
    """


def _identity_table(comparison: dict) -> str:
    identity = comparison.get("identity") or {}
    before = identity.get("before") or {}
    after = identity.get("after") or {}
    rows = [
        ("Repository", before.get("repository"), after.get("repository")),
        ("Target SHA", before.get("target_sha"), after.get("target_sha")),
        ("Analyzer version", before.get("analyzer_version"), after.get("analyzer_version")),
        ("Analyzer source", before.get("analyzer_source_sha"), after.get("analyzer_source_sha")),
        ("Canonical scan", before.get("canonical"), after.get("canonical")),
    ]
    return "".join(
        f"<tr><th>{_h(label)}</th><td><code>{_h(left if left is not None else 'unknown')}</code></td>"
        f"<td><code>{_h(right if right is not None else 'unknown')}</code></td></tr>"
        for label, left, right in rows
    )


def _measurement_note(comparison: dict) -> str:
    measurement = comparison.get("measurement") or {}
    reasons = []
    if measurement.get("analyzer_version_changed"):
        reasons.append("analyzer versions differ")
    if measurement.get("analyzer_source_changed"):
        reasons.append("analyzer source revisions differ")
    if measurement.get("canonical_setting_changed"):
        reasons.append("canonical-scan settings differ")
    if reasons:
        return (
            '<div class="notice warn"><strong>Measurement changed.</strong> '
            "This comparison is not perfectly like-for-like because " + _h(", ".join(reasons)) + ". "
            "Structural deltas remain visible, but some change may come from the measuring instrument rather than the target repository.</div>"
        )
    return (
        '<div class="notice good"><strong>Analyzer settings are like-for-like where recorded.</strong> '
        "That makes target-structure change the cleaner interpretation of the deltas below.</div>"
    )


def _fingerprint(comparison: dict, side: str) -> str:
    fingerprint = (comparison.get("fingerprints") or {}).get(side) or {}
    shares = fingerprint.get("category_shares") or {}
    rows = []
    for category, share in sorted(shares.items(), key=lambda item: (-float(item[1]), item[0])):
        width = max(0.0, min(100.0, float(share) * 100))
        rows.append(
            f'<div class="fp-row"><span>{_h(category.replace("-", " ").title())}</span>'
            f'<div class="fp-track"><i style="width:{width:.5f}%"></i></div><strong>{width:.1f}%</strong></div>'
        )
    rows.append(
        f'<div class="fp-row"><span>Far from value</span><div class="fp-track"><i style="width:{float(fingerprint.get("far_from_value_share") or 0)*100:.5f}%"></i></div>'
        f'<strong>{_pct(float(fingerprint.get("far_from_value_share") or 0))}</strong></div>'
    )
    return (
        f'<div class="fingerprint"><h3>{_h(side.title())}</h3>{"".join(rows)}'
        f'<div class="fp-meta"><span>Depth <strong>{int(fingerprint.get("recursive_depth") or 0)}</strong></span>'
        f'<span>Semantic Index <strong>{float(fingerprint.get("semantic_index") or 0):.1f}</strong></span></div></div>'
    )


def _category_table(comparison: dict) -> str:
    rows = []
    changes = comparison.get("category_deltas") or {}
    for category, change in sorted(changes.items(), key=lambda item: (-abs(int(item[1].get("delta") or 0)), item[0])):
        delta = int(change.get("delta") or 0)
        cls = "up" if delta > 0 else "down" if delta < 0 else "same"
        rows.append(
            f'<tr><td>{_h(category.replace("-", " ").title())}</td><td>{int(change.get("before") or 0):,}</td>'
            f'<td>{int(change.get("after") or 0):,}</td><td class="{cls}">{delta:+,}</td></tr>'
        )
    return "".join(rows) or '<tr><td colspan="4">No category counts were available.</td></tr>'


def _crossovers(comparison: dict) -> str:
    rows = []
    for item in comparison.get("crossovers") or []:
        before = item.get("before") or {}
        after = item.get("after") or {}
        rows.append(
            f'<tr><td><code>{_h(item.get("path"))}</code></td>'
            f'<td>{int(before.get("product_lines") or 0):,} / {int(before.get("machinery_lines") or 0):,}</td>'
            f'<td>{int(after.get("product_lines") or 0):,} / {int(after.get("machinery_lines") or 0):,}</td></tr>'
        )
    if not rows:
        return '<p class="muted">No directory crossed from product-dominant to machinery-dominant between these two supplied scans.</p>'
    return '<div class="table-wrap"><table><thead><tr><th>Directory</th><th>Before product / machinery</th><th>After product / machinery</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'


def _chains(comparison: dict) -> str:
    changes = comparison.get("deepest_exact_chains") or {}
    parts = []
    for label in ("added", "removed"):
        chains = changes.get(label) or []
        if chains:
            parts.append(f'<h3>{_h(label.title())}</h3><ul>' + "".join(
                f'<li><code>{_h(chain.get("signature") or "")}</code> <span class="muted">depth {int(chain.get("depth") or 0)}</span></li>'
                for chain in chains
            ) + '</ul>')
    changed = changes.get("changed") or []
    if changed:
        parts.append('<h3>Changed path</h3><ul>' + "".join(
            f'<li><code>{_h(item.get("before", {}).get("signature") or "")}</code> → <code>{_h(item.get("after", {}).get("signature") or "")}</code></li>'
            for item in changed
        ) + '</ul>')
    return "".join(parts) or '<p class="muted">No deepest exact-chain change was detected.</p>'


def build_evolution_report_html(comparison: dict) -> str:
    metrics = comparison.get("metrics") or {}
    product = metrics.get("product_share") or {}
    machinery = metrics.get("machinery_share") or {}
    scaffold = metrics.get("scaffolding_ratio") or {}
    depth = metrics.get("recursive_depth") or {}
    index = metrics.get("semantic_index") or {}
    exact = metrics.get("exact_coverage") or {}
    explanations = comparison.get("structural_explanations") or []
    explanation_html = "".join(f"<li>{_h(item)}</li>" for item in explanations) or '<li>No material structural delta was described.</li>'
    inversion = comparison.get("inversion_hotspots") or {}
    added_inv = inversion.get("added") or []
    removed_inv = inversion.get("removed") or []
    inversion_html = (
        '<div class="split"><div><h3>Added</h3>' + ("".join(f'<code class="path">{_h(path)}</code>' for path in added_inv) or '<span class="muted">None</span>') + '</div>'
        '<div><h3>Removed</h3>' + ("".join(f'<code class="path">{_h(path)}</code>' for path in removed_inv) or '<span class="muted">None</span>') + '</div></div>'
    )
    target_note = ""
    if (comparison.get("measurement") or {}).get("target_sha_changed"):
        target_note = '<div class="notice good">The recorded target SHA changed between scans, so the comparison represents different repository revisions.</div>'

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ouroboros Software Evolution</title>
<style>
:root{{--bg:#0d1117;--panel:#151b23;--line:#303a46;--text:#eef2f6;--muted:#9da9b6;--accent:#78d6b2;--warn:#f3c76b}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top right,#172132 0,var(--bg) 34rem);color:var(--text);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{width:min(1180px,calc(100% - 32px));margin:auto;padding:32px 0 64px}}h1,h2,h3{{line-height:1.15}}h1{{font-size:clamp(28px,5vw,44px);margin-bottom:6px}}h2{{margin-top:0}}.muted{{color:var(--muted)}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;margin:18px 0;box-shadow:0 10px 28px #0003}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px;min-height:108px}}.label{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}.value{{font-size:22px;font-weight:760;margin:8px 0}}.delta{{color:var(--accent)}}
.notice{{border-radius:11px;padding:12px 14px;margin:10px 0;border:1px solid var(--line)}}.notice.warn{{border-color:#f3c76b77;background:#f3c76b12}}.notice.good{{border-color:#78d6b277;background:#78d6b212}}.grid-2,.split{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line)}}th{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}}.table-wrap{{overflow:auto}}code{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;white-space:normal}}.up{{color:#9ce5b7}}.down{{color:#ffb0b0}}.same{{color:var(--muted)}}
.fingerprint{{border:1px solid var(--line);border-radius:12px;padding:14px}}.fp-row{{display:grid;grid-template-columns:150px 1fr 58px;gap:8px;align-items:center;margin:7px 0}}.fp-track{{height:12px;background:#0a0e13;border:1px solid var(--line);border-radius:999px;overflow:hidden}}.fp-track i{{display:block;height:100%;background:var(--accent)}}.fp-meta{{display:flex;gap:20px;flex-wrap:wrap;color:var(--muted);margin-top:13px}}.path{{display:block;margin:5px 0;padding:6px 8px;border:1px solid var(--line);border-radius:8px}}.footer{{text-align:center;color:var(--muted);padding-top:20px}}
@media(max-width:850px){{.cards{{grid-template-columns:1fr 1fr}}.grid-2,.split{{grid-template-columns:1fr}}}}@media(max-width:520px){{main{{width:calc(100% - 20px)}}.cards{{grid-template-columns:1fr}}.fp-row{{grid-template-columns:110px 1fr 50px}}}}
</style></head><body><main>
<header><h1>Software Evolution</h1><div class="muted">Ouroboros {__version__} · comparison of two saved scans</div></header>
<section class="panel"><h2>What are we comparing?</h2>{_measurement_note(comparison)}{target_note}<div class="table-wrap"><table><thead><tr><th>Identity</th><th>Before</th><th>After</th></tr></thead><tbody>{_identity_table(comparison)}</tbody></table></div></section>
<section class="cards">
{_metric_card('Product', product, _pct, _pp)}
{_metric_card('Machinery', machinery, _pct, _pp)}
{_metric_card('Recursive depth', depth, lambda v: str(int(v or 0)), lambda v: 'n/a' if v is None else f'{v:+.0f}')}
{_metric_card('Semantic Index', index, lambda v: f'{float(v or 0):.1f}', lambda v: 'n/a' if v is None else f'{v:+.1f}')}
{_metric_card('Exact coverage', exact, _pct, _pp)}
{_metric_card('Scaffold / product', scaffold, _ratio, _ratio_delta)}
</section>
<section class="panel"><h2>What changed structurally?</h2><ul>{explanation_html}</ul><p class="muted">These statements describe measured change; they do not label growth or reduction as inherently good or bad.</p></section>
<section class="panel"><h2>Anatomy fingerprints</h2><p class="muted">A multidimensional structural identity, deliberately not collapsed into a ranking badge.</p><div class="grid-2">{_fingerprint(comparison,'before')}{_fingerprint(comparison,'after')}</div></section>
<section class="panel"><h2>Category movement</h2><div class="table-wrap"><table><thead><tr><th>Category</th><th>Before LOC</th><th>After LOC</th><th>Delta</th></tr></thead><tbody>{_category_table(comparison)}</tbody></table></div></section>
<section class="panel"><h2>Scaffolding crossover</h2><p class="muted">Directories that were product-dominant in the first supplied scan and machinery-dominant in the second.</p>{_crossovers(comparison)}</section>
<section class="panel"><h2>Inversion hotspots</h2>{inversion_html}</section>
<section class="panel"><h2>Deepest exact chains</h2><p class="muted">Only EXACT relationships participate in canonical topology and recursive depth.</p>{_chains(comparison)}</section>
<div class="footer">Generated by Ouroboros {__version__}. Self-contained HTML; no remote scripts, fonts, analytics, or telemetry.</div>
</main></body></html>"""


def write_evolution_report(comparison: dict, target: str | Path) -> Path:
    destination = Path(target).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_evolution_report_html(comparison), encoding="utf-8")
    return destination.resolve()
