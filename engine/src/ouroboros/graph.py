from __future__ import annotations

from collections import defaultdict, deque
from pathlib import PurePosixPath

from .model import CATEGORY_DISTANCE_BASE, PRODUCT_CATEGORIES, RECURSIVE_CATEGORIES, AuditChain, Component


SOURCE_PREFIXES = ("src/", "lib/", "app/", "source/")


def _normalize_alias(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./").strip("/")


def _module_aliases(component: Component) -> set[str]:
    path = PurePosixPath(component.path)
    stem = path.with_suffix("").as_posix()
    aliases = {stem, stem.replace("/", ".")}
    for prefix in SOURCE_PREFIXES:
        if stem.startswith(prefix):
            stripped = stem[len(prefix):]
            aliases |= {stripped, stripped.replace("/", ".")}
    if path.name in {"__init__.py", "index.js", "index.ts", "index.tsx", "index.jsx"}:
        parent = path.parent.as_posix()
        aliases |= {parent, parent.replace("/", ".")}
    return {_normalize_alias(alias) for alias in aliases if alias}


def _tail(value: str) -> str:
    normalized = _normalize_alias(value).replace("/", ".")
    return normalized.rsplit(".", 1)[-1]


def resolve_dependencies(components: list[Component]) -> dict[str, set[str]]:
    alias_map: dict[str, set[str]] = defaultdict(set)
    tail_map: dict[str, set[str]] = defaultdict(set)
    for component in components:
        for alias in _module_aliases(component):
            alias_map[alias].add(component.path)
            alias_map[alias.replace("/", ".")].add(component.path)
            tail = _tail(alias)
            if len(tail) >= 3:
                tail_map[tail].add(component.path)

    graph: dict[str, set[str]] = {component.path: set() for component in components}
    for component in components:
        current = PurePosixPath(component.path)
        for raw_import in component.imports:
            candidates = {raw_import, raw_import.replace("::", "."), raw_import.replace("/", ".")}
            if raw_import.startswith("."):
                base = current.parent.as_posix().replace("/", ".")
                candidates.add((base + "." + raw_import.lstrip(".")).strip("."))
            matches: set[str] = set()
            for raw_candidate in candidates:
                candidate = _normalize_alias(raw_candidate)
                matches |= alias_map.get(candidate, set())
                matches |= alias_map.get(candidate.replace("/", "."), set())
            if not matches:
                tails = {_tail(candidate) for candidate in candidates}
                for tail in tails:
                    if len(tail) < 3:
                        continue
                    tail_matches = tail_map.get(tail, set())
                    if len(tail_matches) == 1:
                        matches |= tail_matches
            matches.discard(component.path)
            graph[component.path] |= matches
        component.resolved_dependencies = sorted(graph[component.path])
    return graph


def assign_value_distances(components: list[Component], graph: dict[str, set[str]]) -> None:
    undirected: dict[str, set[str]] = {path: set() for path in graph}
    for source, targets in graph.items():
        for target in targets:
            undirected[source].add(target)
            undirected[target].add(source)

    product_paths = [c.path for c in components if c.category in PRODUCT_CATEGORIES]
    distances: dict[str, int] = {}
    queue = deque((path, 0) for path in product_paths)
    while queue:
        path, distance = queue.popleft()
        if path in distances and distances[path] <= distance:
            continue
        distances[path] = distance
        for neighbor in undirected.get(path, ()):
            if neighbor not in distances:
                queue.append((neighbor, distance + 1))

    for component in components:
        structural = distances.get(component.path)
        base = CATEGORY_DISTANCE_BASE[component.category]
        component.value_distance = max(base, structural) if structural is not None else base


def find_audit_chains(
    components: list[Component],
    graph: dict[str, set[str]],
    max_depth: int = 8,
    max_expansions: int = 50_000,
    *,
    warnings: list[str] | None = None,
) -> list[AuditChain]:
    component_by_path = {c.path: c for c in components}
    reverse: dict[str, set[str]] = defaultdict(set)
    for source, targets in graph.items():
        for target in targets:
            reverse[target].add(source)

    chains: list[AuditChain] = []
    expansions = 0
    truncated = False
    visited_states: set[tuple[str, int]] = set()
    for root in components:
        if root.category not in PRODUCT_CATEGORIES or truncated:
            continue
        visited_states = set()
        stack: list[tuple[str, list[str]]] = [(root.path, [root.path])]
        while stack and not truncated:
            current, path = stack.pop()
            depth = len(path) - 1
            if depth >= max_depth:
                continue
            state = (current, depth)
            if state in visited_states:
                continue
            visited_states.add(state)
            for caller in reverse.get(current, ()):
                expansions += 1
                if expansions > max_expansions:
                    truncated = True
                    break
                if caller in path:
                    continue
                caller_component = component_by_path[caller]
                if caller_component.category not in RECURSIVE_CATEGORIES:
                    continue
                next_path = [*path, caller]
                chains.append(AuditChain(paths=next_path, categories=[component_by_path[p].category for p in next_path]))
                stack.append((caller, next_path))

    if truncated and warnings is not None:
        warnings.append(
            f"Audit-chain search reached its {max_expansions:,}-edge safety budget; reported chains are truncated."
        )

    chains.sort(key=lambda c: (c.depth, sum(component_by_path[p].code_lines for p in c.paths)), reverse=True)
    deduped: list[AuditChain] = []
    seen: set[tuple[str, ...]] = set()
    covered_prefixes: set[tuple[str, ...]] = set()
    for chain in chains:
        key = tuple(chain.paths)
        if key in seen or key in covered_prefixes:
            continue
        seen.add(key)
        deduped.append(chain)
        for length in range(1, len(key)):
            covered_prefixes.add(key[:length])
        if len(deduped) >= 25:
            break
    return deduped
