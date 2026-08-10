from __future__ import annotations

import re
from collections import defaultdict, deque
from pathlib import PurePosixPath

from ouroboros.model import MACHINERY_CATEGORIES, PRODUCT_CATEGORIES, RECURSIVE_CATEGORIES, Category

from .model import EdgeKind, ParseDiagnostic, Resolution, SemanticChain, SemanticEdge, SemanticGraph, SemanticMetrics, Symbol, SymbolKind


_GRAPH_EDGE_KINDS = {EdgeKind.CALLS, EdgeKind.IMPORTS, EdgeKind.INHERITS, EdgeKind.IMPLEMENTS, EdgeKind.REFERENCES}
_DISTANCE_EDGE_KINDS = _GRAPH_EDGE_KINDS | {EdgeKind.CONTAINS}

# Public scoring constants. Changing them is an analyzer-version change.
SEMANTIC_INDEX_AUDIT_WEIGHT = 0.40
SEMANTIC_INDEX_META_WEIGHT = 0.25
SEMANTIC_INDEX_FAR_WEIGHT = 0.20
SEMANTIC_INDEX_DEPTH_WEIGHT = 0.15
SEMANTIC_INDEX_META_MULTIPLIER = 2.0
SEMANTIC_INDEX_DEPTH_NORMALIZER = 6.0
DEFAULT_CHAIN_EXPANSION_BUDGET = 100_000
_SOURCE_PREFIXES = ("src/", "lib/", "app/", "source/")


def _module_aliases(path_value: str) -> set[str]:
    path = PurePosixPath(path_value)
    stem = path.with_suffix("").as_posix().removeprefix("./")
    aliases = {stem, stem.replace("/", ".")}
    for prefix in _SOURCE_PREFIXES:
        if stem.startswith(prefix):
            stripped = stem[len(prefix):]
            aliases |= {stripped, stripped.replace("/", ".")}
    if path.name in {"__init__.py", "index.js", "index.ts", "index.tsx", "index.jsx"}:
        parent = path.parent.as_posix().removeprefix("./")
        aliases |= {parent, parent.replace("/", ".")}
    return {alias for alias in aliases if alias and alias != "."}


def _symbol_refs(symbol: Symbol) -> set[str]:
    refs = {symbol.qualified_name, symbol.name}
    for module in _module_aliases(symbol.path):
        refs.add(f"{module}.{symbol.qualified_name}".strip("."))
    return {_normalize_target(ref) for ref in refs if ref}


def _import_targets(raw: str) -> set[str]:
    """Extract plausible module names from a static import statement/reference."""
    raw = raw.strip()
    targets = set(re.findall(r"[\"']([^\"']+)[\"']", raw))
    normalized = _normalize_target(raw)
    if normalized:
        targets.add(normalized)
    for match in re.finditer(r"\b(?:from|import|using|open|use)\s+([.\w:/-]+)", raw):
        targets.add(match.group(1))
    return {_normalize_module_target(target) for target in targets if target}


def _normalize_module_target(target: str) -> str:
    value = target.strip().strip(";(){}[]\"'")
    value = value.replace("::", ".").replace("\\", "/")
    value = re.sub(r"^(?:\.\.?/)+", "", value)
    value = value.rsplit("/", 1)[-1] if value.startswith("@") else value
    return value.replace("/", ".").strip(".")


def _path_matches_import(path: str, targets: set[str]) -> bool:
    aliases = {_normalize_module_target(alias) for alias in _module_aliases(path)}
    for target in targets:
        if not target:
            continue
        for alias in aliases:
            if target == alias:
                return True
            if target.startswith(alias + ".") or alias.startswith(target + "."):
                return True
    return False


def resolve_relationships(graph: SemanticGraph, file_dependencies: dict[str, set[str]] | None = None) -> None:
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    by_ref: dict[str, list[Symbol]] = defaultdict(list)
    by_path: dict[str, list[Symbol]] = defaultdict(list)
    for symbol in graph.symbols.values():
        if symbol.kind == SymbolKind.FILE:
            by_path[symbol.path].append(symbol)
            continue
        by_name[symbol.name].append(symbol)
        by_name[symbol.qualified_name].append(symbol)
        for ref in _symbol_refs(symbol):
            by_ref[ref].append(symbol)

    for edge in graph.edges:
        if edge.target_id is not None or edge.kind == EdgeKind.CONTAINS:
            continue
        source = graph.symbols.get(edge.source_id)
        if source is None:
            continue

        if edge.kind == EdgeKind.IMPORTS and file_dependencies:
            import_targets = _import_targets(edge.target_name)
            candidate_paths = [
                path for path in file_dependencies.get(source.path, set())
                if _path_matches_import(path, import_targets)
            ]
            file_candidates = [symbol for path in candidate_paths for symbol in by_path.get(path, [])]
            if len(file_candidates) == 1:
                edge.target_id = file_candidates[0].id
                edge.resolution = Resolution.EXACT
                edge.evidence += "; exact local module dependency matches import target"
                continue
            if file_candidates:
                edge.target_id = sorted(file_candidates, key=lambda s: s.path)[0].id
                edge.resolution = Resolution.PROBABLE
                edge.evidence += "; multiple local module dependencies match import target"
                continue

        target = _normalize_target(edge.target_name)
        if not target:
            edge.resolution = Resolution.UNRESOLVED
            continue

        if "." in target:
            candidates = _unique_symbols(by_ref.get(target, []))
            same_language = [c for c in candidates if c.language == source.language]
            same_path = [c for c in same_language if c.path == source.path]
            if len(same_path) == 1:
                edge.target_id = same_path[0].id
                edge.resolution = Resolution.EXACT
            elif len(same_language) == 1:
                edge.target_id = same_language[0].id
                edge.resolution = Resolution.EXACT
            elif same_language:
                edge.target_id = sorted(same_language, key=lambda s: (s.path, s.start_line, s.qualified_name))[0].id
                edge.resolution = Resolution.PROBABLE
            elif candidates:
                edge.target_id = sorted(candidates, key=lambda s: (s.path, s.start_line, s.qualified_name))[0].id
                edge.resolution = Resolution.PROBABLE
            else:
                edge.resolution = Resolution.UNRESOLVED
            continue

        candidates = _unique_symbols(by_name.get(target, []))
        if not candidates:
            edge.resolution = Resolution.UNRESOLVED
            continue

        same_path = [candidate for candidate in candidates if candidate.path == source.path]
        same_parent = [candidate for candidate in same_path if candidate.parent_id == source.parent_id]
        same_language = [candidate for candidate in candidates if candidate.language == source.language]

        if len(same_parent) == 1:
            edge.target_id = same_parent[0].id
            edge.resolution = Resolution.EXACT
        elif len(same_path) == 1:
            edge.target_id = same_path[0].id
            edge.resolution = Resolution.EXACT
        elif len(same_language) == 1:
            edge.target_id = same_language[0].id
            edge.resolution = Resolution.PROBABLE
        elif same_language:
            edge.target_id = sorted(same_language, key=lambda s: (s.path, s.start_line, s.qualified_name))[0].id
            edge.resolution = Resolution.PROBABLE
        else:
            edge.target_id = sorted(candidates, key=lambda s: (s.path, s.start_line, s.qualified_name))[0].id
            edge.resolution = Resolution.PROBABLE


def _canonical_edges(graph: SemanticGraph, *, include_contains: bool = False):
    kinds = _DISTANCE_EDGE_KINDS if include_contains else _GRAPH_EDGE_KINDS
    return (
        edge for edge in graph.edges
        if edge.kind in kinds and edge.target_id is not None and edge.resolution == Resolution.EXACT
    )


def assign_symbol_value_distances(graph: SemanticGraph) -> None:
    adjacency: dict[str, set[str]] = {symbol_id: set() for symbol_id in graph.symbols}
    for edge in _canonical_edges(graph, include_contains=True):
        if edge.source_id not in adjacency or edge.target_id not in adjacency:
            continue
        adjacency[edge.source_id].add(edge.target_id)
        adjacency[edge.target_id].add(edge.source_id)

    roots = [
        symbol.id for symbol in graph.symbols.values()
        if symbol.category in PRODUCT_CATEGORIES and symbol.kind != SymbolKind.FILE
    ]
    if not roots:
        roots = [
            symbol.id for symbol in graph.symbols.values()
            if symbol.category in PRODUCT_CATEGORIES and symbol.kind == SymbolKind.FILE
        ]

    queue: deque[tuple[str, int]] = deque((root, 0) for root in roots)
    seen: dict[str, int] = {}
    while queue:
        symbol_id, distance = queue.popleft()
        if symbol_id in seen and seen[symbol_id] <= distance:
            continue
        seen[symbol_id] = distance
        graph.symbols[symbol_id].value_distance = distance
        for neighbor in adjacency.get(symbol_id, ()):
            queue.append((neighbor, distance + 1))


def find_recursive_chains(graph: SemanticGraph, max_depth: int = 12, max_expansions: int = DEFAULT_CHAIN_EXPANSION_BUDGET) -> list[SemanticChain]:
    reverse: dict[str, list[SemanticEdge]] = defaultdict(list)
    for edge in _canonical_edges(graph):
        reverse[edge.target_id].append(edge)

    roots = [
        symbol.id for symbol in graph.symbols.values()
        if symbol.category in PRODUCT_CATEGORIES and symbol.kind != SymbolKind.FILE
    ]
    chains: dict[tuple[str, ...], SemanticChain] = {}
    expansions = 0
    truncated = False
    visited_states: set[tuple[str, int]] = set()

    def walk(current: str, path: list[str], relationships: list[EdgeKind], seen: set[str]) -> None:
        nonlocal expansions, truncated
        if truncated or len(path) - 1 >= max_depth:
            return
        state = (current, len(path) - 1)
        if state in visited_states:
            return
        visited_states.add(state)
        for edge in reverse.get(current, ()):
            if expansions >= max_expansions:
                truncated = True
                return
            expansions += 1
            dependent = edge.source_id
            if dependent in seen:
                continue
            symbol = graph.symbols.get(dependent)
            if symbol is None:
                continue
            new_path = [*path, dependent]
            new_relationships = [*relationships, edge.kind]
            if symbol.category in RECURSIVE_CATEGORIES:
                chain = SemanticChain(
                    symbol_ids=new_path,
                    categories=[graph.symbols[sid].category for sid in new_path],
                    relationships=new_relationships,
                )
                chains[tuple(new_path)] = chain
                walk(dependent, new_path, new_relationships, seen | {dependent})
            elif symbol.category in MACHINERY_CATEGORIES:
                walk(dependent, new_path, new_relationships, seen | {dependent})

    for root in roots:
        if truncated:
            break
        walk(root, [root], [], {root})

    graph.chain_expansions = expansions
    graph.chain_truncated = truncated
    if truncated:
        graph.diagnostics.append(ParseDiagnostic(
            path="<semantic-graph>", language="graph",
            message=f"Recursive chain traversal reached the safety budget of {max_expansions:,} expansions; depth may be understated.",
            severity="warning",
        ))
    return sorted(chains.values(), key=lambda chain: (-chain.depth, chain.symbol_ids))[:50]


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator


def _optional_ratio(numerator: float, denominator: float) -> float | None:
    if denominator > 0:
        return numerator / denominator
    return None if numerator > 0 else 0.0


def compute_semantic_metrics(graph: SemanticGraph) -> SemanticMetrics:
    symbols = [symbol for symbol in graph.symbols.values() if symbol.kind != SymbolKind.FILE]
    relationships = [edge for edge in graph.edges if edge.kind != EdgeKind.CONTAINS]
    total_symbols = len(symbols)
    resolved = sum(edge.resolution == Resolution.EXACT for edge in relationships)
    probable = sum(edge.resolution == Resolution.PROBABLE for edge in relationships)
    unresolved = sum(edge.resolution == Resolution.UNRESOLVED for edge in relationships)
    product = sum(symbol.category in PRODUCT_CATEGORIES for symbol in symbols)
    machinery = sum(symbol.category in MACHINERY_CATEGORIES for symbol in symbols)
    audit = sum(symbol.category in {Category.AUDIT_PROVENANCE, Category.META_MACHINERY} for symbol in symbols)
    meta = sum(symbol.category == Category.META_MACHINERY for symbol in symbols)
    reachable = sum(symbol.value_distance is not None for symbol in symbols)
    far = sum(
        (symbol.value_distance or 0) >= 4
        for symbol in symbols
        if symbol.value_distance is not None and symbol.category in RECURSIVE_CATEGORIES
    )
    max_distance = max((symbol.value_distance or 0 for symbol in symbols), default=0)
    max_recursive_depth = max((chain.depth for chain in graph.chains), default=0)

    product_share = _ratio(product, total_symbols)
    machinery_share = _ratio(machinery, total_symbols)
    audit_share = _ratio(audit, total_symbols)
    meta_share = _ratio(meta, total_symbols)
    scaffolding_ratio = _optional_ratio(machinery, product)
    far_share = _ratio(far, total_symbols)
    semantic_index = 100.0 * min(
        1.0,
        (SEMANTIC_INDEX_AUDIT_WEIGHT * audit_share)
        + (SEMANTIC_INDEX_META_WEIGHT * meta_share * SEMANTIC_INDEX_META_MULTIPLIER)
        + (SEMANTIC_INDEX_FAR_WEIGHT * far_share)
        + (SEMANTIC_INDEX_DEPTH_WEIGHT * min(max_recursive_depth / SEMANTIC_INDEX_DEPTH_NORMALIZER, 1.0)),
    )

    return SemanticMetrics(
        symbol_count=total_symbols, relationship_count=len(relationships),
        resolved_relationships=resolved, probable_relationships=probable,
        unresolved_relationships=unresolved, product_symbols=product,
        machinery_symbols=machinery, audit_symbols=audit, meta_symbols=meta,
        product_reachable_symbols=reachable, far_from_value_symbols=far,
        max_value_distance=max_distance, max_recursive_depth=max_recursive_depth,
        direct_product_symbol_share=product_share, machinery_symbol_share=machinery_share,
        audit_symbol_share=audit_share, meta_symbol_share=meta_share,
        scaffolding_symbol_ratio=scaffolding_ratio, far_from_value_symbol_share=far_share,
        resolution_rate=_ratio(resolved + probable, len(relationships)) if relationships else 1.0,
        exact_resolution_rate=_ratio(resolved, len(relationships)) if relationships else 1.0,
        semantic_ouroboros_index=semantic_index,
        chain_expansions=graph.chain_expansions, chain_truncated=graph.chain_truncated,
    )


def finalize_graph(graph: SemanticGraph, file_dependencies: dict[str, set[str]] | None = None, *, max_chain_expansions: int = DEFAULT_CHAIN_EXPANSION_BUDGET) -> SemanticGraph:
    resolve_relationships(graph, file_dependencies=file_dependencies)
    assign_symbol_value_distances(graph)
    graph.chains = find_recursive_chains(graph, max_expansions=max_chain_expansions)
    graph.metrics = compute_semantic_metrics(graph)
    return graph


def _normalize_target(target: str) -> str:
    target = target.strip().strip(";(){}[]")
    target = target.replace("::", ".").replace("->", ".")
    target = re.sub(r"\s+", " ", target)
    if target.startswith(("import ", "from ", "using ", "open ", "use ")):
        return target
    if " " in target:
        target = target.split()[-1]
    return target.strip(".")


def _unique_symbols(symbols):
    seen = set()
    result = []
    for symbol in symbols:
        if symbol.id in seen:
            continue
        seen.add(symbol.id)
        result.append(symbol)
    return result
