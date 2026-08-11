from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def build_drivers_report_html(result: dict[str, Any]) -> str:
    drivers = result.get("drivers") or {}
    file_rows = []
    for row in drivers.get("files") or []:
        file_rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(row.get('path') or ''))}</code></td>"
            f"<td>{html.escape(str(row.get('status') or ''))}</td>"
            f"<td>{html.escape(str(row.get('before_category') or '—'))}</td>"
            f"<td>{html.escape(str(row.get('after_category') or '—'))}</td>"
            f"<td>{int(row.get('before_code_lines') or 0):,}</td>"
            f"<td>{int(row.get('after_code_lines') or 0):,}</td>"
            f"<td>{int(row.get('delta_code_lines') or 0):+,}</td>"
            "</tr>"
        )
    category_rows = []
    for row in drivers.get("categories") or []:
        category_rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('category') or ''))}</td>"
            f"<td>{int(row.get('before') or 0):,}</td>"
            f"<td>{int(row.get('after') or 0):,}</td>"
            f"<td>{int(row.get('delta') or 0):+,}</td>"
            "</tr>"
        )
    explanations = "".join(f"<li>{html.escape(str(item))}</li>" for item in drivers.get("structural_explanations") or [])
    chains = drivers.get("deepest_exact_chains") or {}
    chain_items = []
    for kind in ("added", "removed"):
        for chain in chains.get(kind) or []:
            chain_items.append(f"<li><strong>{kind.title()}:</strong> {html.escape(str(chain.get('signature') or ''))}</li>")
    for pair in chains.get("changed") or []:
        chain_items.append(
            "<li><strong>Changed:</strong> "
            + html.escape(str((pair.get("before") or {}).get("signature") or ""))
            + " → "
            + html.escape(str((pair.get("after") or {}).get("signature") or ""))
            + "</li>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ouroboros Change Drivers</title><style>
:root{{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#0e1116;color:#e9edf2}}body{{margin:0;padding:32px}}main{{max-width:1150px;margin:auto}}.lead,.muted{{color:#aeb8c4;line-height:1.55}}.panel{{background:#151a21;border:1px solid #2a333e;border-radius:14px;padding:20px;margin:20px 0;overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:760px}}th,td{{border-bottom:1px solid #28313b;padding:9px 11px;text-align:left}}th{{color:#aeb8c4}}code{{color:#c8e2d7}}.pill{{display:inline-block;border:1px solid #394554;border-radius:999px;padding:5px 10px;margin:0 6px 6px 0}}
</style></head><body><main>
<h1>Ouroboros Change Drivers</h1>
<p class="lead">What concretely moved between two inert canonical repository snapshots. These are observed structural contributors—not blame, causality beyond the adjacent diff, or a quality score.</p>
<div><span class="pill">Before: {html.escape(str((result.get('before') or {}).get('sha') or '')[:10])}</span><span class="pill">After: {html.escape(str((result.get('after') or {}).get('sha') or '')[:10])}</span><span class="pill">Target execution: no</span></div>
<section class="panel"><h2>Largest file contributors</h2><table><thead><tr><th>File</th><th>Status</th><th>Before role</th><th>After role</th><th>Before LOC</th><th>After LOC</th><th>Δ LOC</th></tr></thead><tbody>{''.join(file_rows) or '<tr><td colspan="7">No file-level structural movement observed.</td></tr>'}</tbody></table></section>
<section class="panel"><h2>Category movement</h2><table><thead><tr><th>Category</th><th>Before LOC</th><th>After LOC</th><th>Δ LOC</th></tr></thead><tbody>{''.join(category_rows) or '<tr><td colspan="4">No category movement observed.</td></tr>'}</tbody></table></section>
<section class="panel"><h2>Structural explanation</h2><ul>{explanations or '<li>No tracked structural explanation was produced.</li>'}</ul></section>
<section class="panel"><h2>Deepest exact chain changes</h2><ul>{''.join(chain_items) or '<li>No deepest exact-chain change was observed.</li>'}</ul></section>
<p class="muted">Transport: git archive. Canonical measurement: yes. Remote scripts, fonts, analytics, telemetry: none.</p>
</main></body></html>"""


def write_drivers_report(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_drivers_report_html(result), encoding="utf-8")
    return destination.resolve()
