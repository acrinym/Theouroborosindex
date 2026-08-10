from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from typing import Iterable

from . import __version__
from .model import (
    Analysis,
    Category,
    MACHINERY_CATEGORIES,
    PRODUCT_CATEGORIES,
)
from .semantic.model import Resolution, SemanticEdge, SemanticGraph, Symbol, SymbolKind


CATEGORY_ORDER = (
    Category.CORE_PRODUCT,
    Category.USER_SURFACE,
    Category.ESSENTIAL_SUPPORT,
    Category.TESTING,
    Category.DEVELOPER_TOOLING,
    Category.OBSERVABILITY,
    Category.VERIFICATION,
    Category.AUDIT_PROVENANCE,
    Category.PROCESS_MACHINERY,
    Category.META_MACHINERY,
    Category.DOCUMENTATION,
    Category.UNKNOWN,
)

CATEGORY_LABELS = {
    Category.CORE_PRODUCT: "Core product",
    Category.USER_SURFACE: "User surface",
    Category.ESSENTIAL_SUPPORT: "Essential support",
    Category.DEVELOPER_TOOLING: "Developer tooling",
    Category.TESTING: "Testing",
    Category.OBSERVABILITY: "Observability",
    Category.VERIFICATION: "Verification",
    Category.AUDIT_PROVENANCE: "Audit / provenance",
    Category.PROCESS_MACHINERY: "Process machinery",
    Category.META_MACHINERY: "Meta-machinery",
    Category.DOCUMENTATION: "Documentation",
    Category.UNKNOWN: "Unknown",
}


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}:1"


def _h(value: object) -> str:
    return escape(str(value), quote=True)


def _category_label(value: Category | str) -> str:
    try:
        category = value if isinstance(value, Category) else Category(value)
    except ValueError:
        return str(value)
    return CATEGORY_LABELS.get(category, category.value.replace("-", " ").title())


def _category_class(value: Category | str) -> str:
    raw = value.value if isinstance(value, Category) else str(value)
    return "cat-" + "".join(ch if ch.isalnum() else "-" for ch in raw.lower())


def _share(part: int, total: int) -> float:
    return 0.0 if total <= 0 else part / total


def _summary_sentences(baseline: Analysis, semantic: SemanticGraph) -> list[str]:
    bm = baseline.metrics
    sm = semantic.metrics
    if sm is None:
        return ["Semantic analysis did not produce metrics for this scan."]

    sentences: list[str] = []
    if bm.tooling_share > bm.direct_product_share:
        sentences.append(
            "Surrounding machinery occupies more code than direct product code in this repository."
        )
    elif bm.tooling_share >= 0.35:
        sentences.append(
            "A substantial share of the repository is surrounding machinery, but direct product code remains larger."
        )
    else:
        sentences.append(
            "Direct product code remains larger than the repository's surrounding machinery."
        )

    if sm.max_recursive_depth == 0:
        sentences.append(
            "No exact recursive machinery chain was found in the semantic topology."
        )
    elif sm.max_recursive_depth == 1:
        sentences.append(
            "Recursive machinery is shallow: the deepest exact semantic chain is one step beyond product value."
        )
    elif sm.max_recursive_depth <= 3:
        sentences.append(
            f"The deepest exact recursive machinery chain reaches depth {sm.max_recursive_depth}; inspect the chain evidence below before drawing conclusions."
        )
    else:
        sentences.append(
            f"Deep recursive machinery is present: the deepest exact semantic chain reaches depth {sm.max_recursive_depth}."
        )

    if sm.exact_resolution_rate < 0.35:
        sentences.append(
            "Exact relationship coverage is limited, so the semantic topology should be read conservatively."
        )
    elif sm.exact_resolution_rate < 0.65:
        sentences.append(
            "Exact relationship coverage is moderate; unresolved dynamic behavior may leave parts of the semantic picture incomplete."
        )
    else:
        sentences.append(
            "Exact relationship coverage is strong enough to make the reported topology comparatively well-supported."
        )

    if baseline.warnings or any(d.severity in {"warning", "error"} for d in semantic.diagnostics):
        sentences.append(
            "The scan produced notes or parser diagnostics; review the trust and coverage section for limitations."
        )
    return sentences


def _category_rows(baseline: Analysis) -> str:
    counts = baseline.metrics.category_code_lines
    total = sum(max(0, int(value)) for value in counts.values())
    rows = []
    ordered = sorted(
        CATEGORY_ORDER,
        key=lambda category: (-int(counts.get(category.value, 0)), CATEGORY_ORDER.index(category)),
    )
    for category in ordered:
        lines = int(counts.get(category.value, 0))
        if lines <= 0:
            continue
        share = _share(lines, total)
        rows.append(
            f"""
            <div class="category-row" data-category="{_h(category.value)}">
              <div class="category-name">
                <span class="swatch {_category_class(category)}"></span>
                <strong>{_h(_category_label(category))}</strong>
              </div>
              <div class="category-lines">{lines:,} code lines</div>
              <div class="category-share">{_pct(share)}</div>
            </div>
            """
        )
    return "\n".join(rows) or '<p class="muted">No categorized code lines were recorded.</p>'


def _stacked_bar(baseline: Analysis) -> str:
    counts = baseline.metrics.category_code_lines
    total = sum(max(0, int(value)) for value in counts.values())
    if total <= 0:
        return '<div class="empty-bar">No code-line composition available</div>'
    segments = []
    for category in CATEGORY_ORDER:
        lines = int(counts.get(category.value, 0))
        if lines <= 0:
            continue
        width = _share(lines, total) * 100
        label = f"{_category_label(category)}: {lines:,} code lines ({width:.1f}%)"
        segments.append(
            f'<div class="segment {_category_class(category)}" style="width:{width:.5f}%" title="{_h(label)}"></div>'
        )
    return '<div class="stacked-bar" aria-label="Repository code-line composition">' + "".join(segments) + "</div>"


def _inversion_rows(baseline: Analysis, limit: int = 12) -> str:
    inversions = [profile for profile in baseline.directory_profiles if profile.is_inversion]
    inversions.sort(
        key=lambda profile: (
            -(profile.machinery_lines - profile.product_lines),
            -(profile.scaffolding_ratio or 0.0),
            profile.path,
        )
    )
    if not inversions:
        return '<p class="good-note">No directory with direct product code has more machinery code than product code.</p>'

    rows = []
    for profile in inversions[:limit]:
        rows.append(
            f"""
            <tr>
              <td><code>{_h(profile.path or ".")}</code></td>
              <td>{profile.product_lines:,}</td>
              <td>{profile.machinery_lines:,}</td>
              <td>{_ratio(profile.scaffolding_ratio)}</td>
              <td>{_pct(profile.tooling_share)}</td>
            </tr>
            """
        )
    extra = len(inversions) - min(len(inversions), limit)
    suffix = f'<p class="muted">Plus {extra} more inversion hotspot(s) in the full JSON result.</p>' if extra else ""
    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr><th>Directory</th><th>Product</th><th>Machinery</th><th>Scaffold / product</th><th>Machinery share</th></tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
      {suffix}
    """


def _edge_lookup(edges: Iterable[SemanticEdge]) -> dict[tuple[str, str], SemanticEdge]:
    result: dict[tuple[str, str], SemanticEdge] = {}
    for edge in edges:
        if edge.target_id and edge.resolution == Resolution.EXACT:
            result[(edge.source_id, edge.target_id)] = edge
    return result


def _symbol_title(symbol: Symbol | None, symbol_id: str) -> str:
    if symbol is None:
        return symbol_id
    return symbol.qualified_name or symbol.name or symbol.id


def _chain_cards(semantic: SemanticGraph, limit: int = 8) -> str:
    if not semantic.chains:
        return '<p class="good-note">No exact recursive machinery chain was found.</p>'

    edges = _edge_lookup(semantic.edges)
    chains = sorted(semantic.chains, key=lambda chain: (-chain.depth, chain.symbol_ids))[:limit]
    cards = []
    for index, chain in enumerate(chains, start=1):
        step_items: list[str] = []
        for position, symbol_id in enumerate(chain.symbol_ids):
            symbol = semantic.symbols.get(symbol_id)
            category = symbol.category if symbol is not None else chain.categories[position]
            title = _symbol_title(symbol, symbol_id)
            path_line = ""
            metadata = ""
            if symbol is not None:
                path_line = f'<code>{_h(symbol.path)}:{symbol.start_line}</code>'
                distance = "unknown" if symbol.value_distance is None else str(symbol.value_distance)
                metadata = (
                    f'<span>{_h(symbol.kind.value)}</span>'
                    f'<span>distance {distance}</span>'
                    f'<span>confidence {symbol.role_confidence:.2f}</span>'
                )
            relation = ""
            if position > 0:
                previous_id = chain.symbol_ids[position - 1]
                edge = edges.get((symbol_id, previous_id))
                relationship = chain.relationships[position - 1].value if position - 1 < len(chain.relationships) else "relationship"
                evidence = edge.evidence if edge is not None and edge.evidence else "exact structural relationship"
                relation = (
                    '<div class="chain-relation">'
                    f'<span>← {_h(relationship)}</span>'
                    f'<small>{_h(evidence)}</small>'
                    "</div>"
                )
            step_items.append(
                f"""
                {relation}
                <div class="chain-step {_category_class(category)}">
                  <div class="chain-step-top">
                    <strong>{_h(title)}</strong>
                    <span class="pill">{_h(_category_label(category))}</span>
                  </div>
                  <div class="chain-path">{path_line}</div>
                  <div class="chain-meta">{metadata}</div>
                </div>
                """
            )
        cards.append(
            f"""
            <details class="chain-card" {"open" if index == 1 else ""}>
              <summary>
                <span>Exact chain #{index}</span>
                <strong>depth {chain.depth}</strong>
              </summary>
              <p class="muted">Shown from product value outward. Relationship arrows point back toward the exact dependency used by the next machinery step.</p>
              <div class="chain-steps">{''.join(step_items)}</div>
            </details>
            """
        )
    return "\n".join(cards)


def _component_evidence(baseline: Analysis, limit: int = 160) -> str:
    components = sorted(
        baseline.components,
        key=lambda component: (
            component.category not in MACHINERY_CATEGORIES,
            -(component.value_distance or 0),
            -component.code_lines,
            component.path,
        ),
    )
    rows = []
    for component in components[:limit]:
        signals = component.signals[:8]
        signal_html = "".join(
            f"<li><strong>{_h(_category_label(signal.category))}</strong> "
            f"({_h(f'{signal.weight:+.2f}')}) — {_h(signal.reason)}</li>"
            for signal in signals
        )
        if not signal_html:
            signal_html = "<li>No classifier signal was retained for this file.</li>"
        distance = "—" if component.value_distance is None else str(component.value_distance)
        search_text = f"{component.path} {component.language} {component.category.value}".lower()
        rows.append(
            f"""
            <details class="evidence-card searchable" data-search="{_h(search_text)}" data-category="{_h(component.category.value)}">
              <summary>
                <span class="evidence-path"><code>{_h(component.path)}</code></span>
                <span class="pill {_category_class(component.category)}">{_h(_category_label(component.category))}</span>
                <span>{component.code_lines:,} LOC</span>
                <span>confidence {component.confidence:.2f}</span>
                <span>distance {distance}</span>
              </summary>
              <div class="evidence-body">
                <div><strong>Language:</strong> {_h(component.language)}</div>
                <div><strong>Imports observed:</strong> {_h(", ".join(component.imports[:20]) or "none")}</div>
                <div><strong>Resolved file dependencies:</strong> {_h(", ".join(component.resolved_dependencies[:20]) or "none")}</div>
                <div><strong>Why this file landed here:</strong></div>
                <ul>{signal_html}</ul>
              </div>
            </details>
            """
        )
    extra = len(components) - min(len(components), limit)
    footer = (
        f'<p class="muted">Showing the {limit} highest-priority file evidence records; {extra} additional file(s) remain in the JSON result.</p>'
        if extra
        else ""
    )
    return "\n".join(rows) + footer


def _symbol_evidence(semantic: SemanticGraph, limit: int = 180) -> str:
    symbols = [symbol for symbol in semantic.symbols.values() if symbol.kind != SymbolKind.FILE]
    symbols.sort(
        key=lambda symbol: (
            symbol.category not in MACHINERY_CATEGORIES,
            -(symbol.value_distance or 0),
            -symbol.role_confidence,
            symbol.path,
            symbol.start_line,
            symbol.qualified_name,
        )
    )
    rows = []
    for symbol in symbols[:limit]:
        distance = "—" if symbol.value_distance is None else str(symbol.value_distance)
        search_text = (
            f"{symbol.qualified_name} {symbol.path} {symbol.language} "
            f"{symbol.category.value} {symbol.role_source}"
        ).lower()
        rows.append(
            f"""
            <details class="evidence-card searchable" data-search="{_h(search_text)}" data-category="{_h(symbol.category.value)}">
              <summary>
                <span class="evidence-path"><code>{_h(symbol.qualified_name)}</code></span>
                <span class="pill {_category_class(symbol.category)}">{_h(_category_label(symbol.category))}</span>
                <span>{_h(symbol.kind.value)}</span>
                <span>confidence {symbol.role_confidence:.2f}</span>
                <span>distance {distance}</span>
              </summary>
              <div class="evidence-body">
                <div><strong>Location:</strong> <code>{_h(symbol.path)}:{symbol.start_line}-{symbol.end_line}</code></div>
                <div><strong>Language:</strong> {_h(symbol.language)}</div>
                <div><strong>Role source:</strong> <code>{_h(symbol.role_source)}</code></div>
                <div><strong>Canonical value distance:</strong> {distance}</div>
              </div>
            </details>
            """
        )
    extra = len(symbols) - min(len(symbols), limit)
    footer = (
        f'<p class="muted">Showing the {limit} highest-priority symbol evidence records; {extra} additional symbol(s) remain in the JSON result.</p>'
        if extra
        else ""
    )
    return "\n".join(rows) + footer


def _diagnostics(semantic: SemanticGraph, baseline: Analysis, limit: int = 50) -> str:
    items = []
    for warning in baseline.warnings:
        items.append(("warning", "<baseline>", warning))
    for diagnostic in semantic.diagnostics:
        items.append((diagnostic.severity, diagnostic.path, diagnostic.message))
    if not items:
        return '<p class="good-note">No scan warnings or semantic parser diagnostics were recorded.</p>'
    rows = []
    for severity, path, message in items[:limit]:
        rows.append(
            f"""
            <div class="diagnostic diagnostic-{_h(severity)}">
              <span class="pill">{_h(severity)}</span>
              <code>{_h(path)}</code>
              <span>{_h(message)}</span>
            </div>
            """
        )
    extra = len(items) - min(len(items), limit)
    if extra:
        rows.append(f'<p class="muted">{extra} additional diagnostic(s) are available in the JSON result.</p>')
    return "\n".join(rows)


def build_report_html(repository: str | Path, baseline: Analysis, semantic: SemanticGraph) -> str:
    sm = semantic.metrics
    if sm is None:
        raise ValueError("semantic graph has no metrics")

    repo = str(repository)
    repo_name = Path(repo).name or repo
    total_lines = sum(max(0, int(value)) for value in baseline.metrics.category_code_lines.values())
    category_counts = baseline.metrics.category_code_lines
    machinery_lines = sum(int(category_counts.get(category.value, 0)) for category in MACHINERY_CATEGORIES)
    product_lines = sum(int(category_counts.get(category.value, 0)) for category in PRODUCT_CATEGORIES)
    diagnostic_counts = Counter(d.severity for d in semantic.diagnostics)
    summary = "".join(f"<li>{_h(sentence)}</li>" for sentence in _summary_sentences(baseline, semantic))

    exact = sm.resolved_relationships
    probable = sm.probable_relationships
    unresolved = sm.unresolved_relationships
    relationships = sm.relationship_count
    exact_width = _share(exact, relationships) * 100
    probable_width = _share(probable, relationships) * 100
    unresolved_width = _share(unresolved, relationships) * 100

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ouroboros Repository Anatomy — {_h(repo_name)}</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #0d1117;
  --panel: #151b23;
  --panel-2: #1b2330;
  --text: #eef2f6;
  --muted: #9da9b6;
  --line: #303a46;
  --accent: #78d6b2;
  --accent-2: #b99cff;
  --good: #8ee6a8;
  --warn: #f3c76b;
  --danger: #ff8f8f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: radial-gradient(circle at top right, #172132 0, var(--bg) 34rem);
  color: var(--text);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
main {{ width: min(1220px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 64px; }}
header {{
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 18px;
  align-items: center;
  margin-bottom: 24px;
}}
.mark {{
  width: 68px; height: 68px; border-radius: 50%;
  display: grid; place-items: center;
  font-size: 34px;
  border: 1px solid var(--line);
  background: linear-gradient(145deg, #1c2d2b, #171b27);
  box-shadow: 0 14px 34px #0007;
}}
h1, h2, h3 {{ margin: 0; line-height: 1.15; }}
h1 {{ font-size: clamp(26px, 5vw, 42px); }}
h2 {{ font-size: 23px; margin-bottom: 14px; }}
h3 {{ font-size: 17px; }}
.subtitle, .muted {{ color: var(--muted); }}
.subtitle {{ margin-top: 6px; }}
.panel {{
  background: color-mix(in srgb, var(--panel) 94%, transparent);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  margin: 18px 0;
  box-shadow: 0 10px 28px #0003;
}}
.cards {{
  display: grid;
  grid-template-columns: repeat(6, minmax(130px, 1fr));
  gap: 10px;
  margin: 18px 0;
}}
.card {{
  min-height: 106px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px;
}}
.card .value {{ font-size: 27px; font-weight: 760; margin-top: 7px; }}
.card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
.read-first {{
  border-left: 4px solid var(--accent);
  padding-left: 18px;
}}
.read-first ul {{ margin-bottom: 0; }}
.stacked-bar, .relationship-bar {{
  display: flex;
  overflow: hidden;
  width: 100%;
  min-height: 28px;
  border-radius: 999px;
  background: #0a0e13;
  border: 1px solid var(--line);
}}
.segment {{ min-width: 2px; }}
.category-list {{ display: grid; gap: 7px; margin-top: 16px; }}
.category-row {{
  display: grid;
  grid-template-columns: minmax(170px, 1fr) auto 76px;
  gap: 12px;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid #ffffff0c;
}}
.category-name {{ display: flex; align-items: center; gap: 9px; }}
.swatch {{ width: 13px; height: 13px; border-radius: 4px; display: inline-block; }}
.pill {{
  display: inline-flex;
  align-items: center;
  border: 1px solid #ffffff22;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
  white-space: nowrap;
}}
.cat-core-product {{ background: #2f8f72; }}
.cat-user-surface {{ background: #57b894; }}
.cat-essential-support {{ background: #4f7fab; }}
.cat-testing {{ background: #a987db; }}
.cat-developer-tooling {{ background: #d59a55; }}
.cat-observability {{ background: #d0709c; }}
.cat-verification {{ background: #c9ad54; }}
.cat-audit-provenance {{ background: #d26969; }}
.cat-process-machinery {{ background: #b85f7b; }}
.cat-meta-machinery {{ background: #a54f4f; }}
.cat-documentation {{ background: #6f7b87; }}
.cat-unknown {{ background: #4a5058; }}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }}
.big-number {{ font-size: 34px; font-weight: 800; }}
.metric-line {{ display: flex; justify-content: space-between; gap: 12px; padding: 6px 0; border-bottom: 1px solid #ffffff0c; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }}
th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
code {{
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: #d9e7f2;
  white-space: normal;
  overflow-wrap: anywhere;
}}
.good-note {{
  padding: 12px 14px;
  border: 1px solid #8ee6a855;
  background: #8ee6a811;
  border-radius: 10px;
}}
.chain-card, .evidence-card {{
  border: 1px solid var(--line);
  background: var(--panel-2);
  border-radius: 12px;
  margin: 9px 0;
  overflow: hidden;
}}
summary {{
  cursor: pointer;
  list-style: none;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
}}
summary::-webkit-details-marker {{ display: none; }}
summary::before {{ content: "›"; color: var(--accent); font-size: 20px; transition: transform .15s ease; }}
details[open] > summary::before {{ transform: rotate(90deg); }}
.chain-card > .muted {{ padding: 0 14px; }}
.chain-steps {{ padding: 8px 14px 16px; }}
.chain-step {{
  padding: 11px 12px;
  border-radius: 10px;
  border-left: 4px solid #ffffff55;
  background: #0d1117aa;
}}
.chain-step-top {{ display: flex; gap: 10px; justify-content: space-between; align-items: start; }}
.chain-meta {{ display: flex; gap: 12px; color: var(--muted); font-size: 12px; margin-top: 5px; flex-wrap: wrap; }}
.chain-path {{ margin-top: 5px; }}
.chain-relation {{ display: grid; gap: 2px; margin: 5px 0 5px 22px; color: var(--accent-2); }}
.chain-relation small {{ color: var(--muted); }}
.toolbar {{ display: flex; gap: 9px; flex-wrap: wrap; margin-bottom: 12px; }}
.toolbar input {{
  flex: 1 1 300px;
  background: #0c1118;
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
}}
.filter-button {{
  border: 1px solid var(--line);
  color: var(--text);
  background: var(--panel-2);
  border-radius: 999px;
  padding: 8px 11px;
  cursor: pointer;
}}
.filter-button.active {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
.evidence-card summary {{
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto auto auto auto;
}}
.evidence-body {{ padding: 0 16px 15px; display: grid; gap: 8px; }}
.diagnostic {{
  display: grid;
  grid-template-columns: auto minmax(120px, .4fr) 1fr;
  gap: 10px;
  align-items: start;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
}}
.diagnostic-error {{ color: #ffd1d1; }}
.diagnostic-warning {{ color: #ffe2a1; }}
.exact-segment {{ background: var(--accent); }}
.probable-segment {{ background: var(--warn); }}
.unresolved-segment {{ background: #596270; }}
.relationship-legend {{ display: flex; gap: 18px; flex-wrap: wrap; margin-top: 10px; color: var(--muted); }}
.relationship-legend strong {{ color: var(--text); }}
.section-note {{ margin-top: -6px; color: var(--muted); }}
.footer {{ color: var(--muted); text-align: center; padding: 22px 0; }}
.hidden {{ display: none !important; }}
@media (max-width: 980px) {{
  .cards {{ grid-template-columns: repeat(3, 1fr); }}
  .grid-2 {{ grid-template-columns: 1fr; }}
  .evidence-card summary {{ grid-template-columns: 1fr auto; }}
  .evidence-card summary > span:nth-child(n+3) {{ display: none; }}
}}
@media (max-width: 560px) {{
  main {{ width: min(100% - 20px, 1220px); padding-top: 20px; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); }}
  .category-row {{ grid-template-columns: 1fr auto; }}
  .category-lines {{ display: none; }}
  header {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<main>
<header>
  <div class="mark" aria-hidden="true">🐍</div>
  <div>
    <h1>Repository Anatomy</h1>
    <div class="subtitle"><strong>{_h(repo_name)}</strong> · {_h(repo)} · Ouroboros {_h(__version__)}</div>
  </div>
</header>

<section class="cards" aria-label="Key repository measurements">
  <div class="card"><div class="label">Product code</div><div class="value">{_pct(baseline.metrics.direct_product_share)}</div><div class="muted">{product_lines:,} code lines</div></div>
  <div class="card"><div class="label">Machinery</div><div class="value">{_pct(baseline.metrics.tooling_share)}</div><div class="muted">{machinery_lines:,} code lines</div></div>
  <div class="card"><div class="label">Scaffold / product</div><div class="value">{_ratio(baseline.metrics.scaffolding_ratio)}</div><div class="muted">file/code view</div></div>
  <div class="card"><div class="label">Recursive depth</div><div class="value">{sm.max_recursive_depth}</div><div class="muted">exact semantic chains</div></div>
  <div class="card"><div class="label">Semantic Index</div><div class="value">{sm.semantic_ouroboros_index:.1f}</div><div class="muted">out of 100</div></div>
  <div class="card"><div class="label">Exact coverage</div><div class="value">{_pct(sm.exact_resolution_rate)}</div><div class="muted">{exact:,} exact relationships</div></div>
</section>

<section class="panel read-first">
  <h2>What Ouroboros found</h2>
  <ul>{summary}</ul>
  <p class="muted">This report explains composition and exact structural evidence. It is not a quality grade and does not imply that tests, verification, or tooling should be removed.</p>
</section>

<section class="panel">
  <h2>Where did the product go?</h2>
  <p class="section-note">All {total_lines:,} categorized code lines, shown by purpose.</p>
  {_stacked_bar(baseline)}
  <div class="category-list">{_category_rows(baseline)}</div>
</section>

<section class="grid-2">
  <div class="panel">
    <h2>Two different questions</h2>
    <div class="metric-line"><span>Product + essential support</span><strong>{_pct(baseline.metrics.product_plus_essential_share)}</strong></div>
    <div class="metric-line"><span>Surrounding machinery</span><strong>{_pct(baseline.metrics.tooling_share)}</strong></div>
    <div class="metric-line"><span>Audit + meta code</span><strong>{_pct(baseline.metrics.audit_ratio)}</strong></div>
    <div class="metric-line"><span>File-level recursive depth</span><strong>{baseline.metrics.max_audit_depth}</strong></div>
    <div class="metric-line"><span>File-level Ouroboros Index</span><strong>{baseline.metrics.ouroboros_index:.1f}/100</strong></div>
    <p class="muted">Machinery share asks how much surrounds the product. Recursive depth asks whether machinery has begun supporting machinery. They intentionally remain separate axes.</p>
  </div>
  <div class="panel">
    <h2>Semantic topology</h2>
    <div class="metric-line"><span>Symbols analyzed</span><strong>{sm.symbol_count:,}</strong></div>
    <div class="metric-line"><span>Product symbols</span><strong>{_pct(sm.direct_product_symbol_share)}</strong></div>
    <div class="metric-line"><span>Machinery symbols</span><strong>{_pct(sm.machinery_symbol_share)}</strong></div>
    <div class="metric-line"><span>Far recursive machinery</span><strong>{_pct(sm.far_from_value_symbol_share)}</strong></div>
    <div class="metric-line"><span>Max value distance</span><strong>{sm.max_value_distance}</strong></div>
    <div class="metric-line"><span>Semantic Ouroboros Index</span><strong>{sm.semantic_ouroboros_index:.1f}/100</strong></div>
  </div>
</section>

<section class="panel">
  <h2>Scaffolding inversion hotspots</h2>
  <p class="section-note">Directories that contain product code but now contain more machinery code than direct product code.</p>
  {_inversion_rows(baseline)}
</section>

<section class="panel">
  <h2>Deepest exact chains</h2>
  <p class="section-note">These are the concrete chains behind recursive-depth claims. Only EXACT relationships participate in canonical topology.</p>
  {_chain_cards(semantic)}
</section>

<section class="panel">
  <h2>Trust and coverage</h2>
  <p class="section-note">How much structural relationship evidence the semantic graph could resolve.</p>
  <div class="relationship-bar" aria-label="Relationship resolution">
    <div class="exact-segment" style="width:{exact_width:.5f}%" title="Exact: {exact:,}"></div>
    <div class="probable-segment" style="width:{probable_width:.5f}%" title="Probable: {probable:,}"></div>
    <div class="unresolved-segment" style="width:{unresolved_width:.5f}%" title="Unresolved: {unresolved:,}"></div>
  </div>
  <div class="relationship-legend">
    <span><strong>{exact:,}</strong> exact ({_pct(_share(exact, relationships))})</span>
    <span><strong>{probable:,}</strong> probable ({_pct(_share(probable, relationships))})</span>
    <span><strong>{unresolved:,}</strong> unresolved ({_pct(_share(unresolved, relationships))})</span>
    <span><strong>{diagnostic_counts.get("error", 0)}</strong> parser errors</span>
    <span><strong>{diagnostic_counts.get("warning", 0)}</strong> parser warnings</span>
  </div>
  <div style="margin-top:16px">{_diagnostics(semantic, baseline)}</div>
</section>

<section class="panel">
  <h2>File evidence explorer</h2>
  <p class="section-note">Open a file to see the signals Ouroboros retained for its classification.</p>
  <div class="toolbar">
    <input id="file-search" type="search" placeholder="Filter files by path, language, or category…" aria-label="Filter file evidence">
    <button class="filter-button active" type="button" data-filter-target="files" data-filter="">All</button>
    <button class="filter-button" type="button" data-filter-target="files" data-filter="core-product">Product</button>
    <button class="filter-button" type="button" data-filter-target="files" data-filter="testing">Tests</button>
    <button class="filter-button" type="button" data-filter-target="files" data-filter="audit-provenance">Audit</button>
    <button class="filter-button" type="button" data-filter-target="files" data-filter="meta-machinery">Meta</button>
  </div>
  <div id="file-evidence">{_component_evidence(baseline)}</div>
</section>

<section class="panel">
  <h2>Symbol role explorer</h2>
  <p class="section-note">Inspect symbol-level role, confidence, source, location, and canonical value distance.</p>
  <div class="toolbar">
    <input id="symbol-search" type="search" placeholder="Filter symbols by name, file, role, or language…" aria-label="Filter symbol evidence">
    <button class="filter-button active" type="button" data-filter-target="symbols" data-filter="">All</button>
    <button class="filter-button" type="button" data-filter-target="symbols" data-filter="verification">Verification</button>
    <button class="filter-button" type="button" data-filter-target="symbols" data-filter="audit-provenance">Audit</button>
    <button class="filter-button" type="button" data-filter-target="symbols" data-filter="meta-machinery">Meta</button>
  </div>
  <div id="symbol-evidence">{_symbol_evidence(semantic)}</div>
</section>

<div class="footer">
  Generated locally by Ouroboros {_h(__version__)}. This HTML is self-contained and loads no remote scripts, styles, fonts, or telemetry.
</div>
</main>
<script>
(() => {{
  const state = {{files: "", symbols: ""}};

  function apply(kind) {{
    const container = document.getElementById(kind === "files" ? "file-evidence" : "symbol-evidence");
    const input = document.getElementById(kind === "files" ? "file-search" : "symbol-search");
    const query = input.value.trim().toLowerCase();
    const category = state[kind];
    container.querySelectorAll(".searchable").forEach((item) => {{
      const text = item.dataset.search || "";
      const matchesText = !query || text.includes(query);
      const matchesCategory = !category || item.dataset.category === category;
      item.classList.toggle("hidden", !(matchesText && matchesCategory));
    }});
  }}

  document.getElementById("file-search").addEventListener("input", () => apply("files"));
  document.getElementById("symbol-search").addEventListener("input", () => apply("symbols"));

  document.querySelectorAll("[data-filter-target]").forEach((button) => {{
    button.addEventListener("click", () => {{
      const kind = button.dataset.filterTarget;
      state[kind] = button.dataset.filter || "";
      document.querySelectorAll(`[data-filter-target="${{kind}}"]`).forEach((peer) => peer.classList.remove("active"));
      button.classList.add("active");
      apply(kind);
    }});
  }});
}})();
</script>
</body>
</html>
"""


def write_report(
    repository: str | Path,
    baseline: Analysis,
    semantic: SemanticGraph,
    target: str | Path,
) -> Path:
    destination = Path(target).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        build_report_html(repository, baseline, semantic),
        encoding="utf-8",
    )
    return destination.resolve()
