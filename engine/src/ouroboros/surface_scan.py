from __future__ import annotations

from pathlib import Path

from .classify import classify
from .config import Config, load_config
from .graph import resolve_dependencies
from .scanner import scan_repository
from .semantic import build_semantic_graph


def scan_surface_graph(root: Path, *, use_repo_config: bool):
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {root}")
    config = load_config(root) if use_repo_config else Config()
    scanned = [item for item in scan_repository(root) if not config.ignored(item.component.path)]
    components = [classify(item, override=config.category_for(item.component.path)) for item in scanned]
    file_graph = resolve_dependencies(components)
    semantic = build_semantic_graph(scanned, file_dependencies=file_graph)
    return scanned, semantic
