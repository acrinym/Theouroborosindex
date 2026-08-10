from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class Category(str, Enum):
    CORE_PRODUCT = "core-product"
    USER_SURFACE = "user-surface"
    ESSENTIAL_SUPPORT = "essential-support"
    DEVELOPER_TOOLING = "developer-tooling"
    TESTING = "testing"
    OBSERVABILITY = "observability"
    VERIFICATION = "verification"
    AUDIT_PROVENANCE = "audit-provenance"
    PROCESS_MACHINERY = "process-machinery"
    META_MACHINERY = "meta-machinery"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"


PRODUCT_CATEGORIES = {Category.CORE_PRODUCT, Category.USER_SURFACE}
ESSENTIAL_CATEGORIES = PRODUCT_CATEGORIES | {Category.ESSENTIAL_SUPPORT}
MACHINERY_CATEGORIES = {
    Category.DEVELOPER_TOOLING,
    Category.TESTING,
    Category.OBSERVABILITY,
    Category.VERIFICATION,
    Category.AUDIT_PROVENANCE,
    Category.PROCESS_MACHINERY,
    Category.META_MACHINERY,
}
ASSURANCE_CATEGORIES = {
    Category.TESTING,
    Category.VERIFICATION,
    Category.AUDIT_PROVENANCE,
    Category.META_MACHINERY,
}
RECURSIVE_CATEGORIES = {
    Category.OBSERVABILITY,
    Category.VERIFICATION,
    Category.AUDIT_PROVENANCE,
    Category.PROCESS_MACHINERY,
    Category.META_MACHINERY,
}

CATEGORY_DISTANCE_BASE = {
    Category.CORE_PRODUCT: 0,
    Category.USER_SURFACE: 0,
    Category.ESSENTIAL_SUPPORT: 1,
    Category.TESTING: 2,
    Category.DEVELOPER_TOOLING: 2,
    Category.OBSERVABILITY: 2,
    Category.VERIFICATION: 2,
    Category.DOCUMENTATION: 2,
    Category.AUDIT_PROVENANCE: 3,
    Category.PROCESS_MACHINERY: 3,
    Category.META_MACHINERY: 4,
    Category.UNKNOWN: 2,
}


@dataclass(slots=True)
class Signal:
    category: Category
    weight: float
    reason: str


@dataclass(slots=True)
class Component:
    path: str
    language: str
    lines: int
    code_lines: int
    bytes: int
    category: Category = Category.UNKNOWN
    confidence: float = 0.0
    signals: list[Signal] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    resolved_dependencies: list[str] = field(default_factory=list)
    value_distance: int | None = None

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_dict(self) -> dict:
        data = asdict(self)
        data["category"] = self.category.value
        data["signals"] = [
            {"category": s.category.value, "weight": s.weight, "reason": s.reason}
            for s in self.signals
        ]
        return data


@dataclass(slots=True)
class AuditChain:
    paths: list[str]
    categories: list[Category]

    @property
    def depth(self) -> int:
        return max(0, len(self.paths) - 1)

    def to_dict(self) -> dict:
        return {
            "paths": self.paths,
            "categories": [c.value for c in self.categories],
            "depth": self.depth,
        }


@dataclass(slots=True)
class Metrics:
    direct_product_share: float
    product_plus_essential_share: float
    tooling_share: float
    meta_machinery_share: float
    assurance_ratio: float
    audit_ratio: float
    scaffolding_ratio: float | None
    far_from_value_share: float
    max_audit_depth: int
    ouroboros_index: float
    category_code_lines: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DirectoryProfile:
    path: str
    code_lines: int
    product_lines: int
    essential_lines: int
    machinery_lines: int
    tooling_share: float
    scaffolding_ratio: float | None

    @property
    def is_inversion(self) -> bool:
        return self.product_lines > 0 and self.machinery_lines > self.product_lines

    def to_dict(self) -> dict:
        data = asdict(self)
        data["is_inversion"] = self.is_inversion
        return data


@dataclass(slots=True)
class Analysis:
    root: str
    components: list[Component]
    metrics: Metrics
    audit_chains: list[AuditChain]
    directory_profiles: list[DirectoryProfile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "metrics": self.metrics.to_dict(),
            "audit_chains": [chain.to_dict() for chain in self.audit_chains],
            "directory_profiles": [profile.to_dict() for profile in self.directory_profiles],
            "warnings": self.warnings,
            "components": [component.to_dict() for component in self.components],
        }


def sum_code_lines(components: Iterable[Component], categories: set[Category] | None = None) -> int:
    if categories is None:
        return sum(c.code_lines for c in components)
    return sum(c.code_lines for c in components if c.category in categories)
