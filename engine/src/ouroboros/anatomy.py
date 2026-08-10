from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import PurePosixPath
from typing import Iterable

from .model import Category

FINGERPRINT_CATEGORIES = (
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
)

@dataclass(slots=True)
class LayoutRect:
    kind: str
    path: str
    x: float
    y: float
    width: float
    height: float
    weight: int
    category: str | None = None
    value_distance: int | None = None
    depth: int = 0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "path": self.path,
            "x": round(self.x, 6),
            "y": round(self.y, 6),
            "width": round(self.width, 6),
            "height": round(self.height, 6),
            "weight": self.weight,
            "category": self.category,
            "value_distance": self.value_distance,
            "depth": self.depth,
        }

@dataclass
class _Node:
    path: str
    kind: str = "directory"
    weight: int = 0
    component: object | None = None
    children: dict[str, "_Node"] = field(default_factory=dict)

def anatomy_fingerprint(baseline, semantic) -> dict:
    counts = baseline.metrics.category_code_lines
    total = sum(max(0, int(value)) for value in counts.values())
    category_shares = {
        category.value: (0.0 if total <= 0 else max(0, int(counts.get(category.value, 0))) / total)
        for category in FINGERPRINT_CATEGORIES
    }
    sm = semantic.metrics
    return {
        "category_shares": category_shares,
        "far_from_value_share": 0.0 if sm is None else float(sm.far_from_value_symbol_share),
        "recursive_depth": 0 if sm is None else int(sm.max_recursive_depth),
        "semantic_index": 0.0 if sm is None else float(sm.semantic_ouroboros_index),
    }

def fingerprint_from_payload(payload: dict) -> dict:
    baseline = payload.get("baseline") or {}
    semantic = payload.get("semantic") or {}
    metrics = baseline.get("metrics") or {}
    semantic_metrics = semantic.get("metrics") or {}
    counts = metrics.get("category_code_lines") or {}
    total = sum(max(0, int(value)) for value in counts.values())
    category_shares = {
        category.value: (0.0 if total <= 0 else max(0, int(counts.get(category.value, 0))) / total)
        for category in FINGERPRINT_CATEGORIES
    }
    return {
        "category_shares": category_shares,
        "far_from_value_share": float(semantic_metrics.get("far_from_value_symbol_share") or 0.0),
        "recursive_depth": int(semantic_metrics.get("max_recursive_depth") or 0),
        "semantic_index": float(semantic_metrics.get("semantic_ouroboros_index") or 0.0),
    }

def _build_tree(components: Iterable[object]) -> _Node:
    root = _Node(path=".")
    for component in sorted(components, key=lambda item: item.path):
        weight = max(0, int(component.code_lines))
        if weight <= 0:
            continue
        parts = [part for part in PurePosixPath(component.path).parts if part not in {"", "."}]
        if not parts:
            continue
        node = root
        prefix: list[str] = []
        for part in parts[:-1]:
            prefix.append(part)
            key = "/".join(prefix)
            node = node.children.setdefault(part, _Node(path=key))
        leaf_path = "/".join(parts)
        node.children[parts[-1]] = _Node(path=leaf_path, kind="file", weight=weight, component=component)
    _rollup(root)
    return root

def _rollup(node: _Node) -> int:
    if node.kind == "file":
        return node.weight
    node.weight = sum(_rollup(child) for child in node.children.values())
    return node.weight

def spatial_layout(baseline, *, width: float = 1000.0, height: float = 620.0) -> list[LayoutRect]:
    root = _build_tree(baseline.components)
    if root.weight <= 0:
        return []
    rectangles: list[LayoutRect] = []

    def visit(node: _Node, x: float, y: float, w: float, h: float, depth: int) -> None:
        if node.path != "." and node.kind == "directory":
            rectangles.append(LayoutRect("directory", node.path, x, y, w, h, node.weight, depth=depth))
        if node.kind == "file":
            component = node.component
            rectangles.append(
                LayoutRect(
                    "file", node.path, x, y, w, h, node.weight,
                    category=component.category.value,
                    value_distance=component.value_distance,
                    depth=depth,
                )
            )
            return
        children = sorted(node.children.values(), key=lambda child: (-child.weight, child.path))
        total = sum(child.weight for child in children)
        if total <= 0:
            return
        cursor = 0.0
        split_horizontal = w >= h
        for index, child in enumerate(children):
            fraction = child.weight / total
            if split_horizontal:
                child_w = w - cursor if index == len(children) - 1 else w * fraction
                cx, cy, cw, ch = x + cursor, y, max(0.0, child_w), h
                cursor += child_w
            else:
                child_h = h - cursor if index == len(children) - 1 else h * fraction
                cx, cy, cw, ch = x, y + cursor, w, max(0.0, child_h)
                cursor += child_h
            pad = min(2.5, cw * 0.02, ch * 0.02) if child.kind == "directory" else 0.8
            visit(child, cx + pad, cy + pad, max(0.0, cw - 2 * pad), max(0.0, ch - 2 * pad), depth + 1)

    visit(root, 0.0, 0.0, width, height, 0)
    return rectangles

def _h(value: object) -> str:
    return escape(str(value), quote=True)

def spatial_map_html(baseline, semantic) -> str:
    rectangles = spatial_layout(baseline)
    if not rectangles:
        return '<p class="good-note">No code-line mass was available for a repository map.</p>'

    directory_rects = [rect for rect in rectangles if rect.kind == "directory"]
    file_rects = [rect for rect in rectangles if rect.kind == "file"]
    inversion_paths = {profile.path for profile in baseline.directory_profiles if profile.is_inversion}
    max_depth = max((chain.depth for chain in semantic.chains), default=0)
    deepest_symbol_ids = {
        symbol_id
        for chain in semantic.chains
        if chain.depth == max_depth and max_depth > 0
        for symbol_id in chain.symbol_ids
    }
    deepest_paths = {
        semantic.symbols[symbol_id].path
        for symbol_id in deepest_symbol_ids
        if symbol_id in semantic.symbols
    }
    directory_svg = []
    for rect in sorted(directory_rects, key=lambda item: item.depth):
        if rect.width < 18 or rect.height < 14:
            continue
        label = rect.path if len(rect.path) <= 42 else "…" + rect.path[-39:]
        inversion_class = " map-inversion" if rect.path in inversion_paths else ""
        directory_svg.append(
            f'<g class="map-dir{inversion_class}" data-map-dir="{_h(rect.path)}" tabindex="0" role="button">'
            f'<rect x="{rect.x:.3f}" y="{rect.y:.3f}" width="{rect.width:.3f}" height="{rect.height:.3f}" rx="3" />'
            f'<text x="{rect.x + 4:.3f}" y="{rect.y + 13:.3f}">{_h(label)}</text>'
            '</g>'
        )

    file_svg = []
    for rect in file_rects:
        distance = 0 if rect.value_distance is None else max(0, int(rect.value_distance))
        stroke_width = min(4.5, 0.7 + distance * 0.65)
        title = f"{rect.path} — {rect.weight:,} LOC — {rect.category or 'unknown'} — value distance {distance}"
        css_category = (rect.category or "unknown").replace("_", "-").replace(" ", "-")
        chain_class = " map-chain" if rect.path in deepest_paths else ""
        file_svg.append(
            f'<g class="map-file cat-{_h(css_category)}{chain_class}" data-map-file="{_h(rect.path)}" tabindex="0" role="button">'
            f'<rect x="{rect.x:.3f}" y="{rect.y:.3f}" width="{rect.width:.3f}" height="{rect.height:.3f}" '
            f'rx="2" style="stroke-width:{stroke_width:.2f}px" />'
            f'<title>{_h(title)}</title></g>'
        )

    symbols_by_path: dict[str, list[object]] = {}
    for symbol in semantic.symbols.values():
        if getattr(symbol.kind, "value", str(symbol.kind)) == "file":
            continue
        symbols_by_path.setdefault(symbol.path, []).append(symbol)

    component_by_path = {component.path: component for component in baseline.components}
    directory_records = []
    for directory in sorted({rect.path for rect in directory_rects}):
        descendants = [
            component
            for path, component in component_by_path.items()
            if path == directory or path.startswith(directory.rstrip("/") + "/")
        ]
        descendants.sort(key=lambda component: (-component.code_lines, component.path))
        file_buttons = "".join(
            f'<button type="button" class="map-file-link" data-map-file-link="{_h(component.path)}">'
            f'{_h(component.path)} <span>{component.code_lines:,} LOC</span></button>'
            for component in descendants[:40]
        )
        if len(descendants) > 40:
            file_buttons += f'<span class="muted">+ {len(descendants) - 40} more files in evidence explorer</span>'
        directory_records.append(
            f'<div class="map-directory-record hidden" data-map-directory-record="{_h(directory)}">'
            f'<h3><code>{_h(directory)}</code></h3>'
            f'<p>{sum(component.code_lines for component in descendants):,} LOC across {len(descendants):,} file(s).</p>'
            f'<div class="map-files">{file_buttons}</div>'
            f'<button type="button" class="map-filter-directory" data-map-filter-directory="{_h(directory)}">'
            'Filter this directory in file evidence</button>'
            '</div>'
        )

    records = []
    for path in sorted(component_by_path):
        component = component_by_path[path]
        symbols = sorted(symbols_by_path.get(path, []), key=lambda symbol: (symbol.start_line, symbol.qualified_name))
        symbol_buttons = "".join(
            f'<button type="button" class="map-symbol-link" data-map-symbol="{_h(symbol.qualified_name)}" '
            f'data-map-symbol-path="{_h(symbol.path)}">{_h(symbol.qualified_name)}</button>'
            for symbol in symbols[:30]
        )
        if len(symbols) > 30:
            symbol_buttons += f'<span class="muted">+ {len(symbols) - 30} more in Symbol role explorer</span>'
        if not symbol_buttons:
            symbol_buttons = '<span class="muted">No non-file semantic symbols were emitted for this file.</span>'
        distance = "unknown" if component.value_distance is None else str(component.value_distance)
        records.append(
            f'<div class="map-record hidden" data-map-record="{_h(path)}">'
            f'<h3><code>{_h(path)}</code></h3>'
            f'<p>{component.code_lines:,} LOC · {_h(component.category.value)} · value distance {distance}</p>'
            f'<div class="map-symbols">{symbol_buttons}</div>'
            f'<button type="button" class="map-open-evidence" data-map-evidence="{_h(path)}">Open file evidence</button>'
            '</div>'
        )

    return (
        '<div class="repo-map-layout"><div class="repo-map-wrap">'
        '<svg class="repo-map" viewBox="0 0 1000 620" role="img" aria-label="Spatial repository anatomy">'
        + "".join(directory_svg)
        + "".join(file_svg)
        + '</svg></div><aside class="repo-map-detail" id="repo-map-detail">'
        '<h3>Explore the repository</h3>'
        '<p class="muted">Directories are regions. File area is proportional to code-line mass. Category supplies identity; thicker file borders indicate greater canonical value distance.</p>'
        '<p class="muted">Click a directory, choose a file, then drill into its symbols and the existing evidence explorers.</p>'
        + "".join(directory_records)
        + "".join(records)
        + '</aside></div>'
    )
