from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _h(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_capability_report(payload: dict[str, Any]) -> str:
    atlas = payload["atlas"]
    capabilities = atlas["capabilities"]
    repository = payload.get("repository", "<repository>")
    git_sha = (payload.get("repository_identity") or {}).get("git_sha")
    canonical = bool((payload.get("scan") or {}).get("canonical"))

    cards: list[str] = []
    for capability in capabilities:
        evidence = "".join(
            f"<li><code>{_h(item['path'])}:{item['line']}</code> — {_h(item['detail'])}</li>"
            for item in capability["evidence"]
        )
        files = "".join(f"<li><code>{_h(path)}</code></li>" for path in capability["implementation_files"])
        relationships = "".join(
            "<li>"
            f"<code>{_h(edge['source_id'])}</code> "
            f"<strong>{_h(edge['kind'])}</strong> "
            f"<code>{_h(edge['target_id'])}</code>"
            f"{' — ' + _h(edge['evidence']) if edge['evidence'] else ''}"
            "</li>"
            for edge in capability["exact_relationships"][:80]
        )
        if len(capability["exact_relationships"]) > 80:
            relationships += (
                f"<li>… {len(capability['exact_relationships']) - 80} more exact relationships "
                "remain in the JSON payload.</li>"
            )
        anchor = capability.get("symbol_id") or "unanchored"
        trust_note = (
            f"{len(capability['exact_relationships'])} exact relationship(s); "
            f"{capability['probable_relationships']} probable and "
            f"{capability['unresolved_relationships']} unresolved relationship(s) retained as non-canonical evidence."
        )
        cards.append(
            "<article class='capability'>"
            f"<div class='kind'>{_h(capability['kind'])}</div>"
            f"<h2>{_h(capability['name'])}</h2>"
            f"<p class='anchor'><strong>Anchor:</strong> <code>{_h(anchor)}</code></p>"
            f"<p><strong>Implementation neighborhood:</strong> "
            f"{len(capability['implementation_files'])} file(s), "
            f"{len(capability['implementation_symbols'])} symbol(s).</p>"
            f"<p class='trust'>{_h(trust_note)}</p>"
            "<details open><summary>Discovery evidence</summary><ul>"
            f"{evidence or '<li>No retained discovery evidence.</li>'}</ul></details>"
            "<details><summary>Implementation files</summary><ul>"
            f"{files or '<li>No exact semantic anchor was available.</li>'}</ul></details>"
            "<details><summary>Exact relationships</summary><ul>"
            f"{relationships or '<li>No exact outgoing semantic relationships from the bounded neighborhood.</li>'}"
            "</ul></details>"
            "</article>"
        )

    warnings = "".join(f"<li>{_h(item)}</li>" for item in atlas.get("warnings", []))
    sha_line = f"<p><strong>Target SHA:</strong> <code>{_h(git_sha)}</code></p>" if git_sha else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ouroboros Capability Atlas</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ max-width: 1120px; margin: 0 auto; padding: 2rem; line-height: 1.5; }}
header {{ border-bottom: 1px solid currentColor; margin-bottom: 1.5rem; }}
.summary {{ display: flex; flex-wrap: wrap; gap: .75rem; margin: 1rem 0; }}
.metric {{ border: 1px solid #8888; border-radius: .75rem; padding: .65rem .9rem; min-width: 9rem; }}
.capability {{ border: 1px solid #8888; border-radius: 1rem; padding: 1rem 1.2rem; margin: 1rem 0; }}
.kind {{ text-transform: uppercase; letter-spacing: .08em; font-size: .78rem; opacity: .75; }}
h1, h2 {{ line-height: 1.15; }}
code {{ overflow-wrap: anywhere; }}
details {{ margin-top: .7rem; }}
.trust {{ opacity: .85; }}
.note {{ border-left: .3rem solid currentColor; padding-left: 1rem; }}
</style>
</head>
<body>
<header>
<h1>Ouroboros Capability Atlas</h1>
<p><strong>Repository:</strong> <code>{_h(repository)}</code></p>
{sha_line}
<p><strong>Scan mode:</strong> {"canonical" if canonical else "repository-aware local"}. Target code was not executed.</p>
<div class="summary">
<div class="metric"><strong>{atlas['capability_count']}</strong><br>discovered surfaces</div>
<div class="metric"><strong>{atlas['exact_anchored_count']}</strong><br>semantic anchors</div>
<div class="metric"><strong>{atlas['unanchored_count']}</strong><br>unanchored declarations</div>
</div>
<p class="note">Capability Atlas is descriptive. Exact relationships form implementation neighborhoods.
Probable and unresolved relationships remain visible evidence but do not manufacture canonical topology.</p>
</header>
{"<section><h2>Notes</h2><ul>" + warnings + "</ul></section>" if warnings else ""}
<main>
{"".join(cards) if cards else "<p>No supported capability surface was discovered.</p>"}
</main>
</body>
</html>
"""


def write_capability_report(payload: dict[str, Any], output: str | Path) -> Path:
    target = Path(output).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_capability_report(payload), encoding="utf-8")
    return target.resolve()
