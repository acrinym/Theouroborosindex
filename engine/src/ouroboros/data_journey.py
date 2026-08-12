from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field

from .semantic.model import EdgeKind, Resolution, SemanticGraph, Symbol, SymbolKind


_DATA_KINDS = {
    SymbolKind.TYPE,
    SymbolKind.CLASS,
    SymbolKind.INTERFACE,
    SymbolKind.STRUCT,
    SymbolKind.ENUM,
}
_ROLE_ORDER = {"created": 0, "transformed": 1, "persisted": 2, "emitted": 3}
_CREATE_WORDS = {"create", "new", "build", "make", "parse", "load", "read", "hydrate", "deserialize", "clone", "copy"}
_TRANSFORM_WORDS = {"transform", "map", "normalize", "convert", "adapt", "apply", "merge", "update", "mutate", "replace", "with", "clean", "enrich"}
_PERSIST_WORDS = {"save", "store", "write", "insert", "upsert", "persist", "commit", "serialize", "dump", "archive"}
_EMIT_WORDS = {"emit", "publish", "send", "output", "export", "render", "respond", "response", "yield", "broadcast", "dispatch"}


class DataJourneyError(ValueError):
    pass


@dataclass(slots=True)
class DataJourneySymbol:
    symbol_id: str
    name: str
    qualified_name: str
    path: str
    line: int
    kind: str
    category: str

    @classmethod
    def from_symbol(cls, symbol: Symbol) -> "DataJourneySymbol":
        return cls(
            symbol_id=symbol.id,
            name=symbol.name,
            qualified_name=symbol.qualified_name,
            path=symbol.path,
            line=symbol.start_line,
            kind=symbol.kind.value,
            category=symbol.category.value,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DataLifecycleBoundary:
    role: str
    member: DataJourneySymbol
    evidence: str
    trust: str = "name-derived-role-on-exact-member"

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "member": self.member.to_dict(),
            "evidence": self.evidence,
            "trust": self.trust,
        }


@dataclass(slots=True)
class DataJourneyEvent:
    role: str
    source: DataJourneySymbol
    target: DataJourneySymbol
    relationship: str
    evidence: str
    trust: str

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "relationship": self.relationship,
            "evidence": self.evidence,
            "trust": self.trust,
        }


@dataclass(slots=True)
class DataJourneyAnalysis:
    data_symbol: DataJourneySymbol
    events: list[DataJourneyEvent]
    boundaries: list[DataLifecycleBoundary]
    stage_counts: dict[str, int]
    exact_calls_examined: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "data_symbol": self.data_symbol.to_dict(),
            "interpretation": {
                "event_requirement": "EXACT call relationship",
                "role_assignment": "constructor/type call or lifecycle verb on an EXACT contained member",
                "ordering": "lifecycle role then source location; not runtime chronology",
                "quality_judgment": False,
            },
            "stage_counts": self.stage_counts,
            "exact_calls_examined": self.exact_calls_examined,
            "events": [event.to_dict() for event in self.events],
            "boundaries": [boundary.to_dict() for boundary in self.boundaries],
            "warnings": self.warnings,
        }


def data_symbols(graph: SemanticGraph) -> list[Symbol]:
    return sorted(
        (symbol for symbol in graph.symbols.values() if symbol.kind in _DATA_KINDS),
        key=lambda symbol: (symbol.qualified_name.casefold(), symbol.path, symbol.start_line, symbol.id),
    )


def select_data_symbol(graph: SemanticGraph, selector: str | None) -> Symbol:
    candidates = data_symbols(graph)
    if not candidates:
        raise DataJourneyError("No class, struct, type, interface, or enum symbol is available to follow")

    if selector is None:
        if len(candidates) == 1:
            return candidates[0]
        examples = ", ".join(symbol.qualified_name for symbol in candidates[:8])
        suffix = " …" if len(candidates) > 8 else ""
        raise DataJourneyError(
            "Multiple data-shaped symbols are available; choose one with --data. "
            f"Examples: {examples}{suffix}"
        )

    needle = selector.casefold()
    exact_id = [symbol for symbol in candidates if symbol.id.casefold() == needle]
    if len(exact_id) == 1:
        return exact_id[0]

    exact_qualified = [symbol for symbol in candidates if symbol.qualified_name.casefold() == needle]
    if len(exact_qualified) == 1:
        return exact_qualified[0]
    if len(exact_qualified) > 1:
        choices = ", ".join(f"{symbol.qualified_name} ({symbol.path}:{symbol.start_line})" for symbol in exact_qualified[:8])
        raise DataJourneyError(f"Data selector {selector!r} is ambiguous: {choices}")

    exact_name = [symbol for symbol in candidates if symbol.name.casefold() == needle]
    if len(exact_name) == 1:
        return exact_name[0]
    if len(exact_name) > 1:
        choices = ", ".join(f"{symbol.qualified_name} ({symbol.path}:{symbol.start_line})" for symbol in exact_name[:8])
        raise DataJourneyError(f"Data name {selector!r} is ambiguous: {choices}")

    partial = [
        symbol for symbol in candidates
        if needle in symbol.name.casefold() or needle in symbol.qualified_name.casefold() or needle in symbol.id.casefold()
    ]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        choices = ", ".join(f"{symbol.qualified_name} ({symbol.path}:{symbol.start_line})" for symbol in partial[:8])
        suffix = " …" if len(partial) > 8 else ""
        raise DataJourneyError(f"Data selector {selector!r} matches multiple symbols: {choices}{suffix}")
    raise DataJourneyError(f"No data-shaped symbol matches {selector!r}")


def _words(name: str) -> list[str]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return [part.casefold() for part in re.split(r"[^A-Za-z0-9]+", expanded) if part]


def _member_role(symbol: Symbol) -> str | None:
    if symbol.kind == SymbolKind.CONSTRUCTOR:
        return "created"
    words = _words(symbol.name)
    if not words:
        return None
    first = words[0]
    if first in _CREATE_WORDS:
        return "created"
    if first in _PERSIST_WORDS:
        return "persisted"
    if first in _EMIT_WORDS:
        return "emitted"
    if first in _TRANSFORM_WORDS:
        return "transformed"
    return None


def _event_sort_key(event: DataJourneyEvent) -> tuple:
    return (
        _ROLE_ORDER.get(event.role, 99),
        event.source.path,
        event.source.line,
        event.source.qualified_name,
        event.target.path,
        event.target.line,
        event.target.qualified_name,
    )


def trace_data_journey(data_symbol: Symbol, graph: SemanticGraph) -> DataJourneyAnalysis:
    if data_symbol.id not in graph.symbols:
        raise DataJourneyError(f"Selected data symbol {data_symbol.id!r} is not present in the semantic graph")
    if data_symbol.kind not in _DATA_KINDS:
        raise DataJourneyError(f"Selected symbol {data_symbol.qualified_name!r} is not data-shaped")

    members: dict[str, Symbol] = {}
    for edge in graph.edges:
        if (
            edge.kind == EdgeKind.CONTAINS
            and edge.resolution == Resolution.EXACT
            and edge.source_id == data_symbol.id
            and edge.target_id in graph.symbols
        ):
            member = graph.symbols[edge.target_id]
            if member.kind != SymbolKind.FILE:
                members[member.id] = member

    role_by_member = {
        member_id: role
        for member_id, member in members.items()
        if (role := _member_role(member)) is not None
    }
    boundaries = [
        DataLifecycleBoundary(
            role=role,
            member=DataJourneySymbol.from_symbol(members[member_id]),
            evidence=f"exact member containment; lifecycle verb {members[member_id].name!r}",
        )
        for member_id, role in role_by_member.items()
    ]
    boundaries.sort(key=lambda boundary: (
        _ROLE_ORDER.get(boundary.role, 99),
        boundary.member.path,
        boundary.member.line,
        boundary.member.qualified_name,
    ))

    events: list[DataJourneyEvent] = []
    exact_calls_examined = 0
    seen: set[tuple[str, str, str]] = set()
    for edge in graph.edges:
        if edge.kind != EdgeKind.CALLS or edge.resolution != Resolution.EXACT or edge.target_id is None:
            continue
        exact_calls_examined += 1
        source = graph.symbols.get(edge.source_id)
        target = graph.symbols.get(edge.target_id)
        if source is None or target is None:
            continue

        role: str | None = None
        trust: str | None = None
        evidence = edge.evidence
        if edge.target_id == data_symbol.id:
            role = "created"
            trust = "exact-call-to-data-type"
            evidence = f"{edge.evidence}; exact call resolves to selected {data_symbol.kind.value}"
        elif edge.target_id in role_by_member:
            role = role_by_member[edge.target_id]
            trust = "exact-call-to-lifecycle-member; role-from-member-name"
            evidence = (
                f"{edge.evidence}; exact call resolves to contained member {target.qualified_name!r}; "
                f"role derived from member name {target.name!r}"
            )
        if role is None or trust is None:
            continue

        identity = (role, source.id, target.id)
        if identity in seen:
            continue
        seen.add(identity)
        events.append(DataJourneyEvent(
            role=role,
            source=DataJourneySymbol.from_symbol(source),
            target=DataJourneySymbol.from_symbol(target),
            relationship=EdgeKind.CALLS.value,
            evidence=evidence,
            trust=trust,
        ))

    events.sort(key=_event_sort_key)
    counts = Counter(event.role for event in events)
    stage_counts = {role: counts.get(role, 0) for role in _ROLE_ORDER}
    warnings: list[str] = []
    missing = [role for role in _ROLE_ORDER if not stage_counts[role]]
    if missing:
        warnings.append(
            "No canonical lifecycle event was observed for: " + ", ".join(missing) + ". "
            "Absence means only that the current EXACT-call evidence did not prove that stage."
        )
    unused_boundaries = [
        boundary for boundary in boundaries
        if not any(event.target.symbol_id == boundary.member.symbol_id for event in events)
    ]
    if unused_boundaries:
        warnings.append(
            f"{len(unused_boundaries)} lifecycle-shaped member definition(s) have no observed EXACT caller; "
            "they are listed as boundaries but are not counted as journey events."
        )
    if any(
        edge.kind == EdgeKind.CALLS
        and edge.resolution != Resolution.EXACT
        and (edge.target_id == data_symbol.id or edge.target_id in members)
        for edge in graph.edges
    ):
        warnings.append(
            "Probable or unresolved calls touch this data neighborhood; they are excluded from canonical lifecycle events."
        )

    return DataJourneyAnalysis(
        data_symbol=DataJourneySymbol.from_symbol(data_symbol),
        events=events,
        boundaries=boundaries,
        stage_counts=stage_counts,
        exact_calls_examined=exact_calls_examined,
        warnings=warnings,
    )
