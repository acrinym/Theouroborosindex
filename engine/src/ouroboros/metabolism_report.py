from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any


def _e(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def _short_meta(meta: dict[str, Any] | None) -> str:
    if not meta:
        return "not observed in window"
    return f"{str(meta.get('sha') or '')[:10]} · {_e(meta.get('subject'))}"


def build_metabolism_report_html(result: dict[str, Any]) -> str:
    mass = result["mass"]
    rows = []
    for item in result.get("files") or []:
        status = str(item.get("status") or "unknown")
        if status == "active":
            continue
        kinds = ", ".join((item.get("current_use") or {}).get("kinds") or []) or "none"
        newer = ", ".join(item.get("newer_version_family_siblings") or []) or "—"
        evidence = "<br>".join(_e(line) for line in item.get("status_evidence") or [])
        rows.append(
            "<tr>"
            f"<td><code>{_e(item.get('path'))}</code></td>"
            f"<td>{_e(status)}</td>"
            f"<td>{_e(item.get('purpose'))}</td>"
            f"<td>{int(item.get('code_lines') or 0):,}</td>"
            f"<td>{_short_meta(item.get('last_observed_use'))}</td>"
            f"<td>{_e(kinds)}</td>"
            f"<td>{_e(newer)}</td>"
            f"<td>{evidence}</td>"
            "</tr>"
        )

    frames = []
    for frame in result.get("frames") or []:
        frames.append(
            "<tr>"
            f"<td><code>{_e(str(frame.get('sha') or '')[:10])}</code></td>"
            f"<td>{_e(frame.get('subject'))}</td>"
            f"<td>{int(frame.get('machinery_lines') or 0):,}</td>"
            f"<td>{_pct(frame.get('machinery_share'))}</td>"
            f"<td>{int(frame.get('product_lines') or 0):,}</td>"
            f"<td>{_pct(frame.get('product_share'))}</td>"
            "</tr>"
        )

    payload = base64.b64encode(
        json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    counts = result.get("status_counts") or {}
    pills = "".join(
        f'<span class="pill">{_e(key)}: <strong>{int(value)}</strong></span>'
        for key, value in sorted(counts.items())
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ouroboros Repository Metabolism</title><style>
:root{{color-scheme:dark;font-family:system-ui;background:#0d1117;color:#e6edf3}}body{{margin:0;padding:24px}}main{{max-width:1500px;margin:auto}}.card{{background:#131a22;border:1px solid #2b3541;border-radius:12px;padding:16px;margin:14px 0}}.pills{{display:flex;gap:8px;flex-wrap:wrap}}.pill{{border:1px solid #3c4959;border-radius:999px;padding:6px 10px}}.muted{{color:#9aa7b5}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;border-bottom:1px solid #293440;padding:8px;vertical-align:top}}code{{word-break:break-all}}.scroll{{overflow:auto}}strong.mass{{font-size:1.35rem}}</style></head><body><main>
<h1>Repository Metabolism / Dormancy Atlas</h1>
<p class="muted">Bounded structural-use evidence. This report distinguishes absolute machinery mass from relative share and does not recommend deletion.</p>
<div class="card"><h2>Mass, not just percentage</h2>
<p><strong class="mass">Machinery: {mass['start']['machinery_lines']:,} → {mass['current']['machinery_lines']:,} lines ({mass['delta']['machinery_lines']:+,})</strong><br>
Share: {_pct(mass['start']['machinery_share'])} → {_pct(mass['current']['machinery_share'])} ({mass['delta']['machinery_share']*100:+.1f} pp)</p>
<p><strong class="mass">Product: {mass['start']['product_lines']:,} → {mass['current']['product_lines']:,} lines ({mass['delta']['product_lines']:+,})</strong><br>
Share: {_pct(mass['start']['product_share'])} → {_pct(mass['current']['product_share'])} ({mass['delta']['product_share']*100:+.1f} pp)</p>
<p class="muted">A falling machinery percentage does not mean machinery shrank. The absolute line count is retained beside composition.</p></div>
<div class="card"><h2>Current evidence classes</h2><div class="pills">{pills}</div>
<p class="muted">Dormant, superseded, archive, and bounded-orphan labels are investigation classes. They are not safe-delete claims.</p></div>
<div class="card scroll"><h2>Cleanup-interest evidence</h2><table><thead><tr><th>Path</th><th>Class</th><th>Purpose</th><th>LOC</th><th>Last observed use</th><th>Current use signals</th><th>Newer siblings</th><th>Why</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="8">No non-active files in this bounded result.</td></tr>'}</tbody></table></div>
<div class="card scroll"><h2>Machinery/product mass through the selected history</h2><table><thead><tr><th>Commit</th><th>Subject</th><th>Machinery LOC</th><th>Machinery share</th><th>Product LOC</th><th>Product share</th></tr></thead><tbody>{''.join(frames)}</tbody></table></div>
<div class="card"><h2>Evidence boundary</h2><ul><li>Every selected first-parent commit is scanned from inert <code>git archive</code> input.</li><li>Canonical semantic relationships remain EXACT-only.</li><li>Static workflow/test/manifest path mentions are reported as separate reference evidence, not promoted into canonical semantic topology.</li><li>No observed use inside this window is not proof of no external or older use.</li><li>No target code is executed and no deletion is performed or recommended.</li></ul></div>
</main><script id="metabolism-data" type="application/octet-stream" data-encoding="base64">{payload}</script></body></html>'''


def write_metabolism_report(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_metabolism_report_html(result), encoding="utf-8")
    return destination.resolve()
