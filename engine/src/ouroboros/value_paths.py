from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field

from .capabilities import Capability, CapabilityAtlas
from .semantic.model import EdgeKind, Resolution, SemanticEdge, SemanticGraph


DEFAULT_MAX_DEPTH = 12
MAX_SUPPORTED_DEPTH = 200
DEFAULT_MAX_EXPANSIONS = 50_000
DEFAULT_ALTERNATIVES = 5


class ValuePathError(ValueError):
    pass


@dataclass(slots=True)
class ValuePathStep:
    symbol_id: str
    name: str
    qualified_name: str
    path: str
    line: int
    kind: str
    category: str
    value_distance: int | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ValuePathEdge:
    source_id: str
    target_id: str
    kind: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ValuePath:
    steps: list[ValuePathStep]
    edges: list[ValuePathEdge]
    distinct_files: int
    distinct_categories: int
    probable_call_boundaries: int = 0
    unresolved_call_boundaries: int = 0

    @property
    def depth(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict:
        return {
            "depth": self.depth,
            "distinct_files": self.distinct_files,
            "distinct_categories": self.distinct_categories,
            "probable_call_boundaries": self.probable_call_boundaries,
            "unresolved_call_boundaries": self.unresolved_call_boundaries,
            "steps": [step.to_dict() for step in self.steps],
            "edges": [edge.to_dict() for edge in self.edges],
        }


@dataclass(slots=True)
class ValuePathAnalysis:
    capability: Capability
    strongest: ValuePath
    alternatives: list[ValuePath] = field(default_factory=list)
    expansions: int = 0
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "capability": self.capability.to_dict(),
            "selection": {
                "canonical_relationships": "EXACT CALLS only",
                "strongest_meaning": (
                    "longest bounded exact simple call path; ties prefer more distinct files, "
                    "then more distinct structural categories, then lexical symbol order"
                ),
                "quality_judgment": False,
            },
            "strongest": self.strongest.to_dict(),
            "alternatives": [path.to_dict() for path in self.alternatives],
            "expansions": self.expansions,
            "truncated": self.truncated,
            "warnings": self.warnings,
        }


def select_capability(atlas: CapabilityAtlas, selector: str | None) -> Capability:
    anchored = [capability for capability in atlas.capabilities if capability.symbol_id]
    if not anchored:
        raise ValuePathError("Capability Atlas found no semantically anchored capability to trace")

    if selector is None:
        if len(anchored) == 1:
            return anchored[0]
        names = ", ".join(capability.name for capability in anchored[:8])
        suffix = " …" if len(anchored) > 8 else ""
        raise ValuePathError(
            f"Multiple anchored capabilities are available; choose one with --capability. "
            f"Examples: {names}{suffix}"
        )

    needle = selector.casefold()
    exact_id = [capability for capability in anchored if capability.id.casefold() == needle]
    if len(exact_id) == 1:
        return exact_id[0]

    exact_name = [capability for capability in anchored if capability.name.casefold() == needle]
    if len(exact_name) == 1:
        return exact_name[0]
    if len(exact_name) > 1:
        raise ValuePathError(
            f"Capability name {selector!r} is ambiguous; use the full capability id from --list"
        )

    partial = [
        capability for capability in anchored
        if needle in capability.name.casefold() or needle in capability.id.casefold()
    ]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        choices = ", ".join(capability.name for capability in partial[:8])
        suffix = " …" if len(partial) > 8 else ""
        raise ValuePathError(f"Capability selector {selector!r} matches multiple surfaces: {choices}{suffix}")
    raise ValuePathError(f"No anchored capability matches {selector!r}")


def _step(graph: SemanticGraph, symbol_id: str) -> ValuePathStep:
    symbol = graph.symbols[symbol_id]
    return ValuePathStep(
        symbol_id=symbol.id,
        name=symbol.name,
        qualified_name=symbol.qualified_name,
        path=symbol.path,
        line=symbol.start_line,
        kind=symbol.kind.value,
        category=symbol.category.value,
        value_distance=symbol.value_distance,
    )


def _path(
    graph: SemanticGraph,
    symbol_ids: list[str],
    edges: list[SemanticEdge],
    probable_boundaries: int,
    unresolved_boundaries: int,
) -> ValuePath:
    steps = [_step(graph, symbol_id) for symbol_id in symbol_ids]
    return ValuePath(
        steps=steps,
        edges=[
            ValuePathEdge(
                source_id=edge.source_id,
                target_id=edge.target_id or "",
                kind=edge.kind.value,
                evidence=edge.evidence,
            )
            for edge in edges
        ],
        distinct_files=len({step.path for step in steps}),
        distinct_categories=len({step.category for step in steps}),
        probable_call_boundaries=probable_boundaries,
        unresolved_call_boundaries=unresolved_boundaries,
    )


def _sort_key(path: ValuePath) -> tuple:
    return (
        -path.depth,
        -path.distinct_files,
        -path.distinct_categories,
        tuple(step.symbol_id for step in path.steps),
    )


def trace_value_path(
    capability: Capability,
    graph: SemanticGraph,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_expansions: int = DEFAULT_MAX_EXPANSIONS,
    alternatives: int = DEFAULT_ALTERNATIVES,
) -> ValuePathAnalysis:
    if max_depth < 1:
        raise ValuePathError("max_depth must be at least 1")
    if max_depth > MAX_SUPPORTED_DEPTH:
        raise ValuePathError(f"max_depth cannot exceed {MAX_SUPPORTED_DEPTH}")
    if max_expansions < 1:
        raise ValuePathError("max_expansions must be at least 1")
    if alternatives < 0:
        raise ValuePathError("alternatives cannot be negative")
    if not capability.symbol_id or capability.symbol_id not in graph.symbols:
        raise ValuePathError(f"Capability {capability.name!r} has no exact semantic anchor")

    exact_calls: dict[str, list[SemanticEdge]] = defaultdict(list)
    probable_calls: dict[str, int] = defaultdict(int)
    unresolved_calls: dict[str, int] = defaultdict(int)
    for edge in graph.edges:
        if edge.kind != EdgeKind.CALLS:
            continue
        if edge.resolution == Resolution.EXACT and edge.target_id in graph.symbols:
            exact_calls[edge.source_id].append(edge)
        elif edge.resolution == Resolution.PROBABLE:
            probable_calls[edge.source_id] += 1
        elif edge.resolution == Resolution.UNRESOLVED:
            unresolved_calls[edge.source_id] += 1

    for edges in exact_calls.values():
        edges.sort(key=lambda edge: (edge.target_id or "", edge.evidence))

    completed: list[ValuePath] = []
    expansions = 0
    truncated = False

    def walk(current: str, symbols: list[str], edges: list[SemanticEdge], seen: set[str]) -> None:
        nonlocal expansions, truncated
        outgoing = exact_calls.get(current, [])
        eligible = [edge for edge in outgoing if edge.target_id not in seen]
        hit_depth = len(edges) >= max_depth
        if hit_depth or not eligible:
            completed.append(_path(
                graph,
                symbols,
                edges,
                sum(probable_calls.get(symbol_id, 0) for symbol_id in symbols),
                sum(unresolved_calls.get(symbol_id, 0) for symbol_id in symbols),
            ))
            if hit_depth and eligible:
                truncated = True
            return

        progressed = False
        for edge in eligible:
            if expansions >= max_expansions:
                truncated = True
                break
            expansions += 1
            target_id = edge.target_id
            if target_id is None:
                continue
            progressed = True
            walk(target_id, [*symbols, target_id], [*edges, edge], seen | {target_id})
        if not progressed:
            completed.append(_path(
                graph,
                symbols,
                edges,
                sum(probable_calls.get(symbol_id, 0) for symbol_id in symbols),
                sum(unresolved_calls.get(symbol_id, 0) for symbol_id in symbols),
            ))

    root = capability.symbol_id
    walk(root, [root], [], {root})
    if not completed:
        completed.append(_path(
            graph,
            [root],
            [],
            probable_calls.get(root, 0),
            unresolved_calls.get(root, 0),
        ))

    unique: dict[tuple[str, ...], ValuePath] = {}
    for path in completed:
        unique.setdefault(tuple(step.symbol_id for step in path.steps), path)
    ranked = sorted(unique.values(), key=_sort_key)
    strongest = ranked[0]
    warnings: list[str] = []
    if strongest.depth == 0:
        warnings.append(
            "The selected capability has no outgoing EXACT call relationship. "
            "Ouroboros stops at the anchored surface rather than promoting probable or unresolved calls."
        )
    if truncated:
        warnings.append(
            f"Value-path traversal reached a bound (depth {max_depth} or {max_expansions:,} expansions); "
            "the strongest observed path may be incomplete."
        )
    if strongest.probable_call_boundaries or strongest.unresolved_call_boundaries:
        warnings.append(
            "Probable and unresolved calls were observed along the selected path but were not traversed into canonical flow."
        )

    return ValuePathAnalysis(
        capability=capability,
        strongest=strongest,
        alternatives=ranked[1 : 1 + alternatives],
        expansions=expansions,
        truncated=truncated,
        warnings=warnings,
    )
