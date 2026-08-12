from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _render_steps(path: dict[str, Any]) -> str:
    rows: list[str] = []
    for step in path.get("steps", []):
        rows.append(
            "<li>"
            f"<strong>{_escape(step['qualified_name'])}</strong> "
            f"<code>{_escape(step['path'])}:{step['line']}</code> "
            f"<span>[{_escape(step['category'])}]</span>"
            "</li>"
        )
    return "<ol>" + "".join(rows) + "</ol>" if rows else "<p>No exact call steps.</p>"


def render_value_path_report(payload: dict[str, Any]) -> str:
    analysis = payload["value_path"]
    capability = analysis["capability"]
    strongest = analysis["strongest"]
    alternatives = analysis.get("alternatives", [])
    warnings = analysis.get("warnings", [])

    notes = "".join(f"<li>{_escape(note)}</li>" for note in warnings)
    alt = "".join(
        f"<section><h3>Alternative {index}</h3>"
        f"<p>Depth {path['depth']}; {path['distinct_files']} file(s); "
        f"{path['distinct_categories']} structural category count.</p>"
        f"{_render_steps(path)}</section>"
        for index, path in enumerate(alternatives, 1)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ouroboros Value Path</title>
<style>
body {{ max-width: 1000px; margin: 0 auto; padding: 2rem; font-family: system-ui, sans-serif; line-height: 1.5; }}
code {{ overflow-wrap: anywhere; }}
section {{ border-top: 1px solid #9996; margin-top: 1.5rem; padding-top: 1rem; }}
li {{ margin: .45rem 0; }}
.note {{ border-left: .3rem solid currentColor; padding-left: 1rem; }}
</style>
</head>
<body>
<h1>Ouroboros Value Path</h1>
<p><strong>Repository:</strong> <code>{_escape(payload.get('repository', '<repository>'))}</code></p>
<p><strong>Capability:</strong> [{_escape(capability['kind'])}] {_escape(capability['name'])}</p>
<p><strong>Anchor:</strong> <code>{_escape(capability.get('symbol_id') or 'unanchored')}</code></p>
<p class="note">Canonical Value Paths follow exact call relationships only. Other relationship kinds and lower-trust call evidence remain outside canonical action flow.</p>
<section>
<h2>Strongest exact call path</h2>
<p>Depth {strongest['depth']}; {strongest['distinct_files']} file(s); {strongest['distinct_categories']} structural category count.</p>
{_render_steps(strongest)}
<p>{_escape(analysis['selection']['strongest_meaning'])}. This is descriptive structural evidence, not a quality or importance score.</p>
</section>
{"<section><h2>Notes</h2><ul>" + notes + "</ul></section>" if notes else ""}
<section><h2>Alternative exact terminal paths</h2>{alt or '<p>No alternative exact terminal path was retained.</p>'}</section>
</body>
</html>
"""


def write_value_path_report(payload: dict[str, Any], output: str | Path) -> Path:
    target = Path(output).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_value_path_report(payload), encoding="utf-8")
    return target.resolve()
