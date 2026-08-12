from __future__ import annotations

from html import escape
from pathlib import Path


_ROLE_LABELS = {
    "created": "Created",
    "transformed": "Transformed",
    "persisted": "Persisted",
    "emitted": "Emitted",
}


def _event_card(event: dict) -> str:
    source = event["source"]
    target = event["target"]
    return f"""
    <article class="event">
      <div class="event-head"><strong>{escape(source['qualified_name'])}</strong><span>{escape(event['trust'])}</span></div>
      <div class="location">{escape(source['path'])}:{int(source['line'])}</div>
      <div class="arrow">→ {escape(target['qualified_name'])}</div>
      <div class="evidence">{escape(event['evidence'])}</div>
    </article>
    """


def _boundary_card(boundary: dict) -> str:
    member = boundary["member"]
    return f"""
    <article class="boundary">
      <strong>{escape(_ROLE_LABELS.get(boundary['role'], boundary['role']))}</strong>
      <span>{escape(member['qualified_name'])}</span>
      <small>{escape(member['path'])}:{int(member['line'])}</small>
    </article>
    """


def render_data_journey_report(payload: dict) -> str:
    journey = payload["data_journey"]
    symbol = journey["data_symbol"]
    events = journey.get("events", [])
    boundaries = journey.get("boundaries", [])
    warnings = journey.get("warnings", [])
    by_role = {role: [] for role in _ROLE_LABELS}
    for event in events:
        by_role.setdefault(event["role"], []).append(event)

    stages = []
    for role, label in _ROLE_LABELS.items():
        rows = by_role.get(role, [])
        cards = "".join(_event_card(event) for event in rows) or '<p class="empty">No EXACT-call event proven for this stage.</p>'
        stages.append(f"""
        <section class="stage">
          <header><span class="count">{len(rows)}</span><h2>{label}</h2></header>
          {cards}
        </section>
        """)

    boundary_html = "".join(_boundary_card(boundary) for boundary in boundaries) or '<p class="empty">No lifecycle-shaped contained members detected.</p>'
    warning_html = "".join(f"<li>{escape(warning)}</li>" for warning in warnings) or "<li>No additional caveats.</li>"
    repository = escape(str(payload.get("repository", "")))
    sha = escape(str(payload.get("repository_identity", {}).get("git_sha") or "unavailable"))
    version = escape(str(payload.get("analyzer", {}).get("version", "")))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ouroboros Data Journey — {escape(symbol['qualified_name'])}</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ margin: 0; background: #0d1117; color: #e6edf3; }}
main {{ max-width: 1180px; margin: 0 auto; padding: 42px 24px 64px; }}
h1 {{ margin: 0 0 8px; font-size: clamp(2rem, 5vw, 3.7rem); letter-spacing: -.04em; }}
.kicker {{ color: #7ee787; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
.meta {{ color: #8b949e; line-height: 1.6; overflow-wrap: anywhere; }}
.declaration {{ margin: 28px 0; padding: 20px; border: 1px solid #30363d; border-radius: 14px; background: #161b22; }}
.journey {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; align-items: start; }}
.stage {{ border: 1px solid #30363d; border-radius: 14px; background: #161b22; overflow: hidden; }}
.stage > header {{ display: flex; gap: 10px; align-items: center; padding: 16px; border-bottom: 1px solid #30363d; }}
.stage h2 {{ font-size: 1rem; margin: 0; }}
.count {{ display: inline-grid; place-items: center; min-width: 28px; height: 28px; border-radius: 999px; background: #238636; font-weight: 800; }}
.event {{ padding: 14px 16px; border-top: 1px solid #21262d; }}
.event:first-of-type {{ border-top: 0; }}
.event-head {{ display: grid; gap: 5px; }}
.event-head span, .evidence, .location, small {{ color: #8b949e; font-size: .82rem; }}
.arrow {{ margin: 8px 0; color: #79c0ff; }}
.evidence {{ line-height: 1.45; }}
.empty {{ color: #8b949e; padding: 16px; margin: 0; font-style: italic; }}
.secondary {{ margin-top: 30px; display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px; }}
.panel {{ border: 1px solid #30363d; border-radius: 14px; background: #161b22; padding: 18px; }}
.panel h2 {{ margin-top: 0; }}
.boundary {{ display: grid; grid-template-columns: 100px 1fr; gap: 4px 10px; padding: 10px 0; border-top: 1px solid #21262d; }}
.boundary:first-of-type {{ border-top: 0; }}
.boundary small {{ grid-column: 2; }}
li {{ margin: 8px 0; line-height: 1.5; }}
footer {{ margin-top: 28px; color: #8b949e; font-size: .85rem; }}
@media (max-width: 900px) {{ .journey {{ grid-template-columns: 1fr 1fr; }} .secondary {{ grid-template-columns: 1fr; }} }}
@media (max-width: 560px) {{ .journey {{ grid-template-columns: 1fr; }} main {{ padding: 28px 16px 48px; }} }}
</style>
</head>
<body>
<main>
  <div class="kicker">Ouroboros Data Journey {version}</div>
  <h1>{escape(symbol['qualified_name'])}</h1>
  <div class="meta">{repository}<br>git {sha}</div>
  <section class="declaration">
    <strong>Declaration</strong><br>
    {escape(symbol['kind'])} · {escape(symbol['path'])}:{int(symbol['line'])} · {escape(symbol['category'])}
  </section>
  <div class="journey">{''.join(stages)}</div>
  <div class="secondary">
    <section class="panel"><h2>Lifecycle-shaped definitions</h2>{boundary_html}</section>
    <section class="panel"><h2>Evidence notes</h2><ul>{warning_html}</ul></section>
  </div>
  <footer>Stages are grouped lifecycle evidence, not runtime chronology. Journey events require EXACT call resolution; lifecycle roles on members are name-derived and explicitly labeled.</footer>
</main>
</body>
</html>
"""


def write_data_journey_report(payload: dict, target: str | Path) -> Path:
    path = Path(target).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_data_journey_report(payload), encoding="utf-8")
    return path
