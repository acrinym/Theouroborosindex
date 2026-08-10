from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from .model import ESSENTIAL_CATEGORIES, MACHINERY_CATEGORIES, PRODUCT_CATEGORIES, Category, Component, DirectoryProfile


def directory_profiles(components: list[Component], max_depth: int = 3, min_code_lines: int = 10) -> list[DirectoryProfile]:
    buckets: dict[str, list[Component]] = defaultdict(list)
    for component in components:
        if component.category == Category.DOCUMENTATION:
            continue
        path = PurePosixPath(component.path)
        parents = path.parts[:-1]
        for depth in range(1, min(max_depth, len(parents)) + 1):
            buckets["/".join(parents[:depth])].append(component)

    profiles: list[DirectoryProfile] = []
    for path, members in buckets.items():
        code = sum(c.code_lines for c in members)
        if code < min_code_lines:
            continue
        product = sum(c.code_lines for c in members if c.category in PRODUCT_CATEGORIES)
        essential = sum(c.code_lines for c in members if c.category in ESSENTIAL_CATEGORIES)
        machinery = sum(c.code_lines for c in members if c.category in MACHINERY_CATEGORIES)
        scaffolding = machinery / product if product else (None if machinery else 0.0)
        profiles.append(DirectoryProfile(
            path=path,
            code_lines=code,
            product_lines=product,
            essential_lines=essential,
            machinery_lines=machinery,
            tooling_share=machinery / code if code else 0.0,
            scaffolding_ratio=scaffolding,
        ))
    profiles.sort(key=lambda p: (p.is_inversion, p.tooling_share, p.code_lines), reverse=True)
    return profiles
