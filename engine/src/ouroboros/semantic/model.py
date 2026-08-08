from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Iterable

from ouroboros.model import Category


class SymbolKind(str, Enum):
    FILE = "file"
    NAMESPACE = "namespace"
    MODULE = "module"
    TYPE = "type"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    TRAIT = "trait"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    PROPERTY = "property"
    VARIABLE = "variable"
    UNKNOWN = "unknown"


class EdgeKind(str, Enum):
    CONTAINS = "contains"
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    REFERENCES = "references"


class Resolution(str, Enum):
    EXACT = "exact"
    PROBABLE = "probable"
    UNRESOLVED = "unresolved"


@dataclass(slots=True)
class Symbol:
    id: str
    path: str
    language: str
    kind: SymbolKind
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    parent_id: str | None = None
    category: Category = Category.UNKNOWN
    value_distance: int | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["category"] = self.category.value
        return data


@dataclass(slots=True)
class SemanticEdge:
    source_id: str
    kind: EdgeKind
    target_name: str
    target_id: str | None = None
    resolution: Resolution = Resolution.UNRESOLVED
    evidence: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["resolution"] = self.resolution.value
        return data


@dataclass(slots=True)
class ParseDiagnostic:
    path: str
    language: str
    message: str
    severity: str = "warning"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ParsedUnit:
    path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    edges: list[SemanticEdge] = field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)


@dataclass(slots=True)
class SemanticMetrics:
    symbol_count: int
    relationship_count: int
    resolved_relationships: int
    probable_relationships: int
    unresolved_relationships: int
    product_symbols: int
    machinery_symbols: int
    product_reachable_symbols: int
    far_from_value_symbols: int
    max_value_distance: int
    max_recursive_depth: int
    direct_product_symbol_share: float
    machinery_symbol_share: float
    far_from_value_symbol_share: float
    resolution_rate: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SemanticChain:
    symbol_ids: list[str]
    categories: list[Category]

    @property
    def depth(self) -> int:
        return max(0, len(self.symbol_ids) - 1)

    def to_dict(self) -> dict:
        return {
            "symbol_ids": self.symbol_ids,
            "categories": [category.value for category in self.categories],
            "depth": self.depth,
        }


@dataclass(slots=True)
class SemanticGraph:
    symbols: dict[str, Symbol] = field(default_factory=dict)
    edges: list[SemanticEdge] = field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)
    chains: list[SemanticChain] = field(default_factory=list)
    metrics: SemanticMetrics | None = None

    def add_symbols(self, symbols: Iterable[Symbol]) -> None:
        for symbol in symbols:
            self.symbols[symbol.id] = symbol

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "chains": [chain.to_dict() for chain in self.chains],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "symbols": [symbol.to_dict() for symbol in self.symbols.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }
