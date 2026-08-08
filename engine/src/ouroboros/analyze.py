from __future__ import annotations

from pathlib import Path

from .classify import classify
from .config import load_config
from .graph import assign_value_distances, find_audit_chains, resolve_dependencies
from .metrics import compute_metrics
from .model import Analysis, Category
from .profiles import directory_profiles
from .scanner import scan_repository


def analyze_repository(path: str | Path) -> Analysis:
    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {root}")

    config = load_config(root)
    scanned = [item for item in scan_repository(root) if not config.ignored(item.component.path)]
    components = [classify(item, override=config.category_for(item.component.path)) for item in scanned]
    graph = resolve_dependencies(components)
    assign_value_distances(components, graph)
    chains = find_audit_chains(components, graph)
    metrics = compute_metrics(components, chains)
    profiles = directory_profiles(components)

    warnings: list[str] = []
    if not components:
        warnings.append("No supported text/code files were found.")
    unknown_loc = sum(c.code_lines for c in components if c.category == Category.UNKNOWN)
    total_loc = sum(c.code_lines for c in components if c.category != Category.DOCUMENTATION)
    if total_loc and unknown_loc / total_loc > 0.20:
        warnings.append("More than 20% of code lines are unclassified; interpret ratios cautiously.")

    components.sort(key=lambda c: (c.category.value, -c.code_lines, c.path))
    return Analysis(
        root=str(root),
        components=components,
        metrics=metrics,
        audit_chains=chains,
        directory_profiles=profiles,
        warnings=warnings,
    )
