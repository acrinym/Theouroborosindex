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


def _short(value: object) -> str:
    return "unknown" if not value else str(value)[:10]


def _map(frame: dict[str, Any]) -> str:
    colors = {
        "core-product": "#4ecdc4", "user-surface": "#7bdff2", "essential-support": "#5e8cff",
        "testing": "#f6bd60", "developer-tooling": "#f28482", "observability": "#84a59d",
        "verification": "#cdb4db", "audit-provenance": "#b8c0ff", "process-machinery": "#ff9f1c",
        "meta-machinery": "#e76f51",
    }
    changed = {str(row.get("path")) for row in (frame.get("delta") or {}).get("changes") or []}
    dirs, files = [], []
    for row in (frame.get("map") or {}).get("rectangles") or []:
        attrs = f'x="{float(row.get("x") or 0):.3f}" y="{float(row.get("y") or 0):.3f}" width="{max(0.0, float(row.get("width") or 0)):.3f}" height="{max(0.0, float(row.get("height") or 0)):.3f}"'
        if row.get("kind") == "directory":
            dirs.append(f'<rect class="dir" {attrs}/>')
            continue
        path = str(row.get("path") or "")
        stroke = ' class="changed"' if path in changed else ""
        title = _e(f"{path} — {int(row.get('weight') or 0)} LOC — {row.get('category') or 'unknown'}")
        files.append(f'<rect{stroke} {attrs} fill="{colors.get(str(row.get("category")), "#6b7785")}"><title>{title}</title></rect>')
    return f'<svg viewBox="0 0 1000 620"><g>{"".join(dirs)}</g><g>{"".join(files)}</g></svg>'


def _frame(frame: dict[str, Any], index: int, total: int, events: list[dict[str, Any]]) -> str:
    delta = frame.get("delta") or {}
    summary = delta.get("summary") or {}
    metrics = [
        ("product", _pct(frame.get("product_share"))), ("machinery", _pct(frame.get("machinery_share"))),
        ("exact depth", int(frame.get("recursive_depth") or 0)), ("Semantic Index", f"{float(frame.get('semantic_index') or 0):.1f}"),
        ("exact coverage", _pct(frame.get("exact_coverage"))), ("mapped files", int((frame.get("map") or {}).get("file_count") or 0)),
    ]
    counts = [(label, int(summary.get(key) or 0)) for label, key in [
        ("appeared", "appeared"), ("disappeared", "disappeared"), ("grew", "grew"), ("shrunk", "shrunk"),
        ("category changed", "classification_changed"), ("distance changed", "value_distance_changed")]]
    changes = []
    for row in (delta.get("changes") or [])[:30]:
        flags = []
        for key in ("appeared", "disappeared", "grew", "shrunk", "classification_changed", "value_distance_changed"):
            if row.get(key):
                flags.append(key.replace("_", " "))
        changes.append(f'<li><code>{_e(row.get("path"))}</code> — {_e(", ".join(flags))}</li>')
    active_events = [event for event in events if event.get("commit") == frame.get("sha")]
    event_html = "".join(f'<div class="event">{_e(event.get("type"))} — {_e(event.get("subject"))}</div>' for event in active_events) or '<p class="muted">No bounded-history event at this commit.</p>'
    boxes = lambda rows: "".join(f'<span class="box">{_e(a)}: <strong>{_e(v)}</strong></span>' for a, v in rows)
    baseline = '<p class="muted">Baseline frame; no imaginary empty repository is used.</p>' if delta.get("baseline_frame") else ""
    return f'''<section class="frame" data-i="{index}" {'hidden' if index else ''}>
<div class="p"><strong>Frame {index + 1} / {total}</strong> · <code>{_e(_short(frame.get('sha')))}</code> · {_e(frame.get('authored_at'))}<br><strong>{_e(frame.get('subject'))}</strong></div>
<div class="grid"><div class="p"><h2>Repository geography</h2><div class="map">{_map(frame)}</div></div><aside><div class="p"><h2>Measurements</h2><div class="stats">{boxes(metrics)}</div></div><div class="p"><h2>Change from previous frame</h2>{baseline}<div class="stats">{boxes(counts)}</div><ol class="changes">{"".join(changes)}</ol></div></aside></div>
<div class="p"><h2>Bounded-history events</h2>{event_html}</div></section>'''


def build_evolution_movie_report_html(result: dict[str, Any]) -> str:
    frames = result.get("frames") or []
    if not frames:
        raise ValueError("Evolution Movie requires at least one frame")
    info = result.get("range") or {}
    body = "".join(_frame(frame, index, len(frames), result.get("events") or []) for index, frame in enumerate(frames))
    payload = base64.b64encode(
        json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ouroboros Evolution Movie</title><style>
:root{{color-scheme:dark;font-family:system-ui;background:#0d1117;color:#e6edf3}}body{{margin:0;padding:24px}}main{{max-width:1400px;margin:auto}}.p{{background:#131a22;border:1px solid #2b3541;border-radius:12px;padding:15px;margin:14px 0}}.muted{{color:#9aa7b5}}.bar,.stats{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}.bar input{{flex:1;min-width:220px}}.box{{border:1px solid #34404e;border-radius:8px;padding:6px 9px}}button,select{{background:#1c2631;color:#e6edf3;border:1px solid #435063;border-radius:8px;padding:8px 11px}}.grid{{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:14px}}.map{{overflow:auto;background:#090e13}}svg{{width:100%;min-width:700px;display:block}}.dir{{fill:none;stroke:#536273}}.changed{{stroke:#fff;stroke-width:2}}.changes{{max-height:350px;overflow:auto}}.event{{border-left:3px solid #7eb69d;padding:5px 8px}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Ouroboros Evolution Movie</h1><p class="muted">Exact bounded first-parent Repository Anatomy over time. Every frame was scanned from inert <code>git archive</code> input. Motion describes structure, not quality.</p>
<div class="stats"><span class="box">Repository: {_e(result.get('repository'))}</span><span class="box">From: {_e(_short(info.get('from_sha')))}</span><span class="box">To: {_e(_short(info.get('to_sha')))}</span><span class="box">Frames: {len(frames)}</span><span class="box">Sampled: no</span></div>
<div class="p bar"><button id="play">▶ Play</button><input id="range" type="range" min="0" max="{len(frames)-1}" value="0" aria-label="Evolution frame"><select id="speed" aria-label="Playback speed"><option value="1400">Slow</option><option value="900" selected>Normal</option><option value="500">Fast</option></select></div>{body}
</main><script id="movie-data" type="application/octet-stream" data-encoding="base64">{payload}</script><script>(()=>{{const f=[...document.querySelectorAll('.frame')],r=document.querySelector('#range'),p=document.querySelector('#play'),s=document.querySelector('#speed');let t=null;const show=i=>{{f.forEach((x,n)=>x.hidden=n!==i);r.value=i}},stop=()=>{{clearInterval(t);t=null;p.textContent='▶ Play'}},start=()=>{{stop();p.textContent='⏸ Pause';t=setInterval(()=>show((+r.value+1)%f.length),+s.value)}};r.oninput=()=>{{stop();show(+r.value)}};p.onclick=()=>t?stop():start;s.onchange=()=>{{if(t)start()}}}})();</script></body></html>'''


def write_evolution_movie_report(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_evolution_movie_report_html(result), encoding="utf-8")
    return destination.resolve()
