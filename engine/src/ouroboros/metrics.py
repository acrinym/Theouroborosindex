from __future__ import annotations

from collections import defaultdict

from .model import (
    ASSURANCE_CATEGORIES,
    ESSENTIAL_CATEGORIES,
    MACHINERY_CATEGORIES,
    PRODUCT_CATEGORIES,
    AuditChain,
    Category,
    Component,
    Metrics,
    sum_code_lines,
)


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator


def compute_metrics(components: list[Component], audit_chains: list[AuditChain]) -> Metrics:
    code_components = [c for c in components if c.category != Category.DOCUMENTATION]
    total = sum_code_lines(code_components)
    product = sum_code_lines(code_components, PRODUCT_CATEGORIES)
    essential = sum_code_lines(code_components, ESSENTIAL_CATEGORIES)
    machinery = sum_code_lines(code_components, MACHINERY_CATEGORIES)
    assurance = sum_code_lines(code_components, ASSURANCE_CATEGORIES)
    audit = sum_code_lines(code_components, {Category.AUDIT_PROVENANCE, Category.META_MACHINERY})
    meta = sum_code_lines(code_components, {Category.META_MACHINERY})
    far = sum(c.code_lines for c in code_components if (c.value_distance or 0) >= 4)
    max_depth = max((chain.depth for chain in audit_chains), default=0)

    category_lines: dict[str, int] = defaultdict(int)
    for component in components:
        category_lines[component.category.value] += component.code_lines

    direct_product_share = _ratio(product, total)
    product_plus_essential_share = _ratio(essential, total)
    tooling_share = _ratio(machinery, total)
    meta_share = _ratio(meta, total)
    assurance_ratio = _ratio(assurance, essential)
    audit_ratio = _ratio(audit, total)
    scaffolding_ratio = _ratio(machinery, product)
    far_share = _ratio(far, total)

    # Descriptive 0-100 signal, never a moral quality grade.
    ouroboros = 100.0 * min(
        1.0,
        (0.40 * audit_ratio)
        + (0.25 * meta_share * 2.0)
        + (0.20 * far_share)
        + (0.15 * min(max_depth / 6.0, 1.0)),
    )

    return Metrics(
        direct_product_share=direct_product_share,
        product_plus_essential_share=product_plus_essential_share,
        tooling_share=tooling_share,
        meta_machinery_share=meta_share,
        assurance_ratio=assurance_ratio,
        audit_ratio=audit_ratio,
        scaffolding_ratio=scaffolding_ratio,
        far_from_value_share=far_share,
        max_audit_depth=max_depth,
        ouroboros_index=ouroboros,
        category_code_lines=dict(sorted(category_lines.items())),
    )
