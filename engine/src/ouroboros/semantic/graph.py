from __future__ import annotations

from collections import defaultdict, deque

from ouroboros.model import MACHINERY_CATEGORIES, PRODUCT_CATEGORIES, RECURSIVE_CATEGORIES, Category

from .model import EdgeKind, Resolution, SemanticChain, SemanticEdge, SemanticGraph, SemanticMetrics, Symbol, SymbolKind


_GRAPH_EDGE_KINDS = {EdgeKind.CALLS, EdgeKind.IMPORTS, EdgeKind.INHERITS, EdgeKind.IMPLEMENTS, EdgeKind.REFERENCES}

# Public scoring constants. These stay fixed for an analyzer version so published
# corpus scores remain comparable; changing them is an analyzer-version change,
# not a per-repository tuning knob.
SEMANTIC_INDEX_AUDIT_WEIGHT = 0.40
SEMANTIC_INDEX_META_WEIGHT = 0.25
SEMANTIC_INDEX_FAR_WEIGHT = 0.20
SEMANTIC_INDEX_DEPTH_WEIGHT = 0.15
SEMANTIC_INDEX_META_MULTIPLIER = 2.0
SEMANTIC_INDEX_DEPTH_NORMALIZER = 6.0


def resolve_relationships(graph: SemanticGraph, file_dependencies: dict[str, set[str]] | None = None) -> None:
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    by_tail: dict[str, list[Symbol]] = defaultdict(list)
    by_path: dict[str, list[Symbol]] = defaultdict(list)
    for symbol in graph.symbols.values():
        if symbol.kind == SymbolKind.FILE:
            by_path[symbol.path].append(symbol)
            continue
        by_name[symbol.qualified_name].append(symbol)
        by_name[symbol.name].append(symbol)
        by_tail[symbol.qualified_name.rsplit(".", 1)[-1]].append(symbol)

    for edge in graph.edges:
        if edge.target_id is not None or edge.kind == EdgeKind.CONTAINS:
            continue
        source = graph.symbols.get(edge.source_id)
        if source is None:
            continue

        # An explicit file dependency is stronger evidence than a textual symbol-name
        # match and may legitimately bridge languages (for example a generated binding).
        if edge.kind == EdgeKind.IMPORTS and file_dependencies:
            candidate_paths = file_dependencies.get(source.path, set())
            file_candidates = [
                symbol for path in candidate_paths
                for symbol in by_path.get(path, [])
            ]
            if len(file_candidates) == 1:
                edge.target_id = file_candidates[0].id
                edge.resolution = Resolution.EXACT
                continue
            if file_candidates:
                edge.target_id = sorted(file_candidates, key=lambda s: s.path)[0].id
                edge.resolution = Resolution.PROBABLE
                continue

        target = _normalize_target(edge.target_name)
        candidates = _unique_symbols(by_name.get(target, []))
        if not candidates:
            tail = target.rsplit(".", 1)[-1]
            candidates = _unique_symbols(by_tail.get(tail, []))

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
            edge.resolution = Resolution.EXACT
        elif same_language:
            edge.target_id = sorted(same_language, key=lambda s: (s.path, s.start_line, s.qualified_name))[0].id
            edge.resolution = Resolution.PROBABLE
        else:
            # A bare name match across languages is never canonical evidence. Keep the
            # candidate visible, but require an adapter or explicit dependency to prove it.
            edge.target_id = sorted(candidates, key=lambda s: (s.path, s.start_line, s.qualified_name))[0].id
            edge.resolution = Resolution.PROBABLE


def _canonical_edges(graph: SemanticGraph):
    """Edges trusted for canonical reachability and recursive depth.

    Probable matches remain in the graph for inspection and coverage reporting, but they are
    never allowed to create product reachability, Distance From Value, or Ouroboros chains.
    """
    return (
        edge for edge in graph.edges
        if edge.kind in _GRAPH_EDGE_KINDS
        and edge.target_id is not None
        and edge.resolution == Resolution.EXACT
    )


def assign_symbol_value_distances(graph: SemanticGraph) -> None:
    adjacency: dict[str, set[str]] = {symbol_id: set() for symbol_id in graph.symbols}
    for edge in _canonical_edges(graph):
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


def find_recursive_chains(graph: SemanticGraph, max_depth: int = 12) -> list[SemanticChain]:
    reverse: dict[str, list[SemanticEdge]] = defaultdict(list)
    for edge in _canonical_edges(graph):
        reverse[edge.target_id].append(edge)

    roots = [
        symbol.id for symbol in graph.symbols.values()
        if symbol.category in PRODUCT_CATEGORIES and symbol.kind != SymbolKind.FILE
    ]
    chains: list[SemanticChain] = []

    def walk(current: str, path: list[str], relationships: list[EdgeKind], seen: set[str]) -> None:
        if len(path) - 1 >= max_depth:
            return
        for edge in reverse.get(current, ()):
            dependent = edge.source_id
            if dependent in seen:
                continue
            symbol = graph.symbols.get(dependent)
            if symbol is None:
                continue
            new_path = path + [dependent]
            new_relationships = relationships + [edge.kind]
            if symbol.category in RECURSIVE_CATEGORIES:
                chains.append(SemanticChain(
                    symbol_ids=new_path,
                    categories=[graph.symbols[sid].category for sid in new_path],
                    relationships=new_relationships,
                ))
                walk(dependent, new_path, new_relationships, seen | {dependent})
            elif symbol.category in MACHINERY_CATEGORIES:
                walk(dependent, new_path, new_relationships, seen | {dependent})

    for root in roots:
        walk(root, [root], [], {root})

    unique: dict[tuple[str, ...], SemanticChain] = {tuple(chain.symbol_ids): chain for chain in chains}
    return sorted(unique.values(), key=lambda chain: (-chain.depth, chain.symbol_ids))[:50]


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator


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
    far = sum((symbol.value_distance or 0) >= 4 for symbol in symbols if symbol.value_distance is not None)
    max_distance = max((symbol.value_distance or 0 for symbol in symbols), default=0)
    max_recursive_depth = max((chain.depth for chain in graph.chains), default=0)

    product_share = _ratio(product, total_symbols)
    machinery_share = _ratio(machinery, total_symbols)
    audit_share = _ratio(audit, total_symbols)
    meta_share = _ratio(meta, total_symbols)
    scaffolding_ratio = _ratio(machinery, product)
    far_share = _ratio(far, total_symbols)
    semantic_index = 100.0 * min(
        1.0,
        (SEMANTIC_INDEX_AUDIT_WEIGHT * audit_share)
        + (SEMANTIC_INDEX_META_WEIGHT * meta_share * SEMANTIC_INDEX_META_MULTIPLIER)
        + (SEMANTIC_INDEX_FAR_WEIGHT * far_share)
        + (
            SEMANTIC_INDEX_DEPTH_WEIGHT
            * min(max_recursive_depth / SEMANTIC_INDEX_DEPTH_NORMALIZER, 1.0)
        ),
    )

    return SemanticMetrics(
        symbol_count=total_symbols,
        relationship_count=len(relationships),
        resolved_relationships=resolved,
        probable_relationships=probable,
        unresolved_relationships=unresolved,
        product_symbols=product,
        machinery_symbols=machinery,
        audit_symbols=audit,
        meta_symbols=meta,
        product_reachable_symbols=reachable,
        far_from_value_symbols=far,
        max_value_distance=max_distance,
        max_recursive_depth=max_recursive_depth,
        direct_product_symbol_share=product_share,
        machinery_symbol_share=machinery_share,
        audit_symbol_share=audit_share,
        meta_symbol_share=meta_share,
        scaffolding_symbol_ratio=scaffolding_ratio,
        far_from_value_symbol_share=far_share,
        resolution_rate=_ratio(resolved + probable, len(relationships)) if relationships else 1.0,
        exact_resolution_rate=_ratio(resolved, len(relationships)) if relationships else 1.0,
        semantic_ouroboros_index=semantic_index,
    )


def finalize_graph(graph: SemanticGraph, file_dependencies: dict[str, set[str]] | None = None) -> SemanticGraph:
    resolve_relationships(graph, file_dependencies=file_dependencies)
    assign_symbol_value_distances(graph)
    graph.chains = find_recursive_chains(graph)
    graph.metrics = compute_semantic_metrics(graph)
    return graph


def _normalize_target(target: str) -> str:
    target = target.strip().strip(";(){}[]")
    target = target.replace("::", ".").replace("->", ".")
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
