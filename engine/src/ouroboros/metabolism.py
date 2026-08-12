from __future__ import annotations

import re
import shutil
import tempfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from .capabilities import build_capability_atlas
from .history import (
    DEFAULT_MAX_COMMITS,
    HARD_MAX_COMMITS,
    HistoryError,
    _git,
    archive_commit,
    commit_metadata,
    first_parent_commits,
    repository_root,
    resolve_commit,
)
from .model import MACHINERY_CATEGORIES, PRODUCT_CATEGORIES, Category
from .semantic import EdgeKind, Resolution
from .surface_scan import scan_surface_graph


_MANIFEST_NAMES = {
    "pyproject.toml", "package.json", "package-lock.json", "cargo.toml", "cargo.lock",
    "go.mod", "go.sum", "pom.xml", "build.gradle", "build.gradle.kts",
    "requirements.txt", "setup.py", "setup.cfg", "makefile", "justfile",
}
_ARCHIVE_WORDS = ("handoff", "archive", "legacy", "history", "historical", "qualification", "release-notes")
_VERSION_FAMILY_RE = re.compile(
    r"(?i)(?P<prefix>.*(?:release|stage|migration|migrate|schema|version|upgrade|v)[_-]?)(?P<num>\d{2,})(?P<suffix>.*)"
)


def _recent_first_parent_commits(root: Path, to_ref: str, count: int) -> list[str]:
    if count < 1 or count > HARD_MAX_COMMITS:
        raise HistoryError("invalid-limit", f"since must be between 1 and {HARD_MAX_COMMITS}")
    end = resolve_commit(root, to_ref)
    rows = [
        line.strip().lower()
        for line in _git(root, "rev-list", "--first-parent", f"--max-count={count}", end).splitlines()
        if line.strip()
    ]
    if not rows:
        raise HistoryError("git-error", f"No first-parent commits found ending at {to_ref!r}")
    return list(reversed(rows))


def _reference_source(path: str, category: Category) -> bool:
    name = PurePosixPath(path).name.lower()
    return (
        path.startswith(".github/")
        or category == Category.TESTING
        or name in _MANIFEST_NAMES
        or name.endswith((".yml", ".yaml")) and ("workflow" in path.lower() or path.startswith(".github/"))
    )


def _snapshot_evidence(scanned: list, semantic) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_path = {item.component.path: item for item in scanned}
    paths = set(by_path)
    signals: dict[str, dict[str, Any]] = {
        path: {
            "exact_semantic_inbound": [],
            "local_dependency_inbound": [],
            "capability_surface": [],
            "capability_reachable": [],
            "static_path_references": [],
        }
        for path in paths
    }

    for edge in semantic.edges:
        if edge.kind == EdgeKind.CONTAINS or edge.resolution != Resolution.EXACT or edge.target_id is None:
            continue
        source = semantic.symbols.get(edge.source_id)
        target = semantic.symbols.get(edge.target_id)
        if source is None or target is None or source.path == target.path or target.path not in signals:
            continue
        signals[target.path]["exact_semantic_inbound"].append(
            {"source": source.path, "kind": edge.kind.value, "evidence": edge.evidence}
        )

    for item in scanned:
        source = item.component.path
        for target in item.component.resolved_dependencies:
            if target in signals and target != source:
                signals[target]["local_dependency_inbound"].append({"source": source})

    atlas = build_capability_atlas(scanned, semantic)
    for capability in atlas.capabilities:
        if capability.path in signals:
            signals[capability.path]["capability_surface"].append(
                {"id": capability.id, "kind": capability.kind, "name": capability.name}
            )
        if capability.symbol_id and capability.symbol_id in semantic.symbols:
            anchored_path = semantic.symbols[capability.symbol_id].path
            if anchored_path in signals:
                signals[anchored_path]["capability_surface"].append(
                    {"id": capability.id, "kind": capability.kind, "name": capability.name}
                )
        for target in capability.implementation_files:
            if target in signals:
                signals[target]["capability_reachable"].append(
                    {"id": capability.id, "kind": capability.kind, "name": capability.name}
                )

    candidates = sorted(paths, key=len, reverse=True)
    for item in scanned:
        source = item.component.path
        if not _reference_source(source, item.component.category):
            continue
        text = item.text
        for target in candidates:
            if target == source:
                continue
            if target in text or f"./{target}" in text:
                signals[target]["static_path_references"].append({"source": source})

    compact: dict[str, dict[str, Any]] = {}
    for path, groups in signals.items():
        restored: dict[str, list[dict[str, str]]] = {}
        for key, rows in groups.items():
            seen: set[tuple[tuple[str, str], ...]] = set()
            unique_rows: list[dict[str, str]] = []
            for row in rows:
                identity = tuple(sorted((str(k), str(v)) for k, v in row.items()))
                if identity in seen:
                    continue
                seen.add(identity)
                unique_rows.append({str(k): str(v) for k, v in row.items()})
            unique_rows.sort(key=lambda row: tuple(sorted(row.items())))
            restored[key] = unique_rows
        active_kinds = [key for key, rows in restored.items() if rows]
        compact[path] = {"active": bool(active_kinds), "kinds": active_kinds, "evidence": restored}

    machinery_lines = sum(
        item.component.code_lines for item in scanned if item.component.category in MACHINERY_CATEGORIES
    )
    product_lines = sum(
        item.component.code_lines for item in scanned if item.component.category in PRODUCT_CATEGORIES
    )
    code_lines = sum(
        item.component.code_lines for item in scanned if item.component.category != Category.DOCUMENTATION
    )
    categories = Counter(item.component.category.value for item in scanned)
    category_lines = Counter()
    for item in scanned:
        category_lines[item.component.category.value] += item.component.code_lines

    return compact, {
        "file_count": len(scanned),
        "code_lines": code_lines,
        "machinery_lines": machinery_lines,
        "product_lines": product_lines,
        "machinery_share": 0.0 if code_lines <= 0 else machinery_lines / code_lines,
        "product_share": 0.0 if code_lines <= 0 else product_lines / code_lines,
        "category_files": dict(sorted(categories.items())),
        "category_code_lines": dict(sorted(category_lines.items())),
        "capability_count": len(atlas.capabilities),
        "capability_warnings": atlas.warnings,
        "semantic_diagnostics": len(semantic.diagnostics),
    }


def _family(path: str) -> tuple[str, int] | None:
    pure = PurePosixPath(path)
    match = _VERSION_FAMILY_RE.fullmatch(pure.stem)
    if match is None:
        return None
    family_stem = f"{match.group('prefix')}{{n}}{match.group('suffix')}".lower()
    return f"{pure.parent.as_posix()}/{family_stem}{pure.suffix.lower()}", int(match.group("num"))


def _newer_siblings(paths: set[str]) -> dict[str, list[str]]:
    families: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for path in paths:
        parsed = _family(path)
        if parsed is not None:
            families[parsed[0]].append((parsed[1], path))
    result: dict[str, list[str]] = {}
    for members in families.values():
        members.sort()
        for number, path in members:
            newer = [other for other_number, other in members if other_number > number]
            if newer:
                result[path] = newer
    return result


def _archive_candidate(path: str, category: Category) -> bool:
    lowered = path.lower()
    return category == Category.DOCUMENTATION and any(word in lowered for word in _ARCHIVE_WORDS)


def _status(
    *,
    path: str,
    category: Category,
    current_active: bool,
    last_use: dict[str, Any] | None,
    observed_frames: int,
    total_frames: int,
    newer: list[str],
) -> tuple[str, list[str]]:
    evidence: list[str] = []
    if current_active:
        evidence.append("supported structural-use evidence is present at the current commit")
        return "active", evidence
    if newer:
        evidence.append("no supported current-use evidence was observed")
        evidence.append("newer version-family sibling(s) are present: " + ", ".join(newer[:5]))
        return "superseded-candidate", evidence
    if _archive_candidate(path, category):
        evidence.append("documentation path carries explicit historical/archive/release semantics")
        evidence.append("no supported current-use evidence was observed")
        return "archive-candidate", evidence
    if last_use is not None:
        evidence.append(f"last supported use in the bounded window was {last_use['sha'][:10]}")
        return "dormant", evidence
    if category in MACHINERY_CATEGORIES and observed_frames >= min(3, total_frames):
        evidence.append(f"no supported use was observed in any of {observed_frames} frame(s) where the file existed")
        evidence.append("classification is machinery, but absence of observed use is not proof of safe deletion")
        return "bounded-orphan-candidate", evidence
    evidence.append("current evidence is insufficient to infer cleanability")
    return "insufficient-evidence", evidence


def scan_repository_metabolism(
    path: str | Path,
    *,
    since: int | None = DEFAULT_MAX_COMMITS,
    from_ref: str | None = None,
    to_ref: str = "HEAD",
    max_commits: int = HARD_MAX_COMMITS,
) -> dict[str, Any]:
    root = repository_root(path)
    if from_ref is not None:
        commits = first_parent_commits(root, from_ref, to_ref, max_commits=max_commits)
        range_mode = "explicit"
    else:
        commits = _recent_first_parent_commits(root, to_ref, DEFAULT_MAX_COMMITS if since is None else since)
        range_mode = "recent-count"

    use_history: dict[str, dict[str, Any]] = {}
    changed_history: dict[str, dict[str, Any]] = {}
    first_seen: dict[str, dict[str, Any]] = {}
    observations: Counter[str] = Counter()
    previous_fingerprint: dict[str, tuple] = {}
    frames: list[dict[str, Any]] = []
    current_scanned = None
    current_signals = None

    with tempfile.TemporaryDirectory(prefix="ouroboros-metabolism-") as temp:
        temp_root = Path(temp)
        for index, sha in enumerate(commits):
            commit_dir = temp_root / f"commit-{index:04d}"
            snapshot = commit_dir / "snapshot"
            acquisition = archive_commit(root, sha, snapshot)
            scanned, semantic = scan_surface_graph(snapshot, use_repo_config=False)
            signals, metrics = _snapshot_evidence(scanned, semantic)
            metadata = commit_metadata(root, sha)

            fingerprint: dict[str, tuple] = {}
            for item in scanned:
                path_value = item.component.path
                observations[path_value] += 1
                fingerprint[path_value] = (
                    item.component.bytes,
                    item.component.code_lines,
                    item.component.category.value,
                )
                first_seen.setdefault(path_value, metadata)
                if index > 0 and (path_value not in previous_fingerprint or previous_fingerprint[path_value] != fingerprint[path_value]):
                    changed_history[path_value] = metadata
                if signals.get(path_value, {}).get("active"):
                    use_history[path_value] = metadata

            frames.append({**metadata, "frame_index": index, "acquisition": acquisition, **metrics})
            previous_fingerprint = fingerprint
            if index == len(commits) - 1:
                current_scanned = scanned
                current_signals = signals
            shutil.rmtree(commit_dir, ignore_errors=True)

    assert current_scanned is not None and current_signals is not None
    current_paths = {item.component.path for item in current_scanned}
    newer_map = _newer_siblings(current_paths)
    files: list[dict[str, Any]] = []

    for item in current_scanned:
        component = item.component
        path_value = component.path
        current = current_signals[path_value]
        last_use = use_history.get(path_value)
        status, status_evidence = _status(
            path=path_value,
            category=component.category,
            current_active=bool(current["active"]),
            last_use=last_use,
            observed_frames=observations[path_value],
            total_frames=len(commits),
            newer=newer_map.get(path_value, []),
        )
        files.append(
            {
                "path": path_value,
                "language": component.language,
                "category": component.category.value,
                "purpose": component.category.value,
                "code_lines": component.code_lines,
                "bytes": component.bytes,
                "status": status,
                "status_evidence": status_evidence,
                "current_use": current,
                "last_observed_use": last_use,
                "first_observed": first_seen.get(path_value),
                "last_observed_change": changed_history.get(path_value),
                "observed_frames": observations[path_value],
                "newer_version_family_siblings": newer_map.get(path_value, []),
            }
        )

    status_counts = Counter(row["status"] for row in files)
    current = frames[-1]
    start = frames[0]
    files.sort(
        key=lambda row: (
            {
                "superseded-candidate": 0,
                "bounded-orphan-candidate": 1,
                "dormant": 2,
                "archive-candidate": 3,
                "insufficient-evidence": 4,
                "active": 5,
            }.get(row["status"], 9),
            -int(row["code_lines"]),
            row["path"],
        )
    )

    return {
        "schema": {"name": "ouroboros-repository-metabolism", "version": 1},
        "repository": str(root),
        "range": {
            "mode": range_mode,
            "from_ref": from_ref,
            "from_sha": commits[0],
            "to_ref": to_ref,
            "to_sha": commits[-1],
            "commits_scanned": len(commits),
            "first_parent": True,
            "sampled": False,
            "history_bound": True,
        },
        "policy": {
            "target_execution": False,
            "network_access": False,
            "history_transport": "git-archive",
            "relationship_topology": "exact-only for canonical semantic relationships",
            "quality_judgment": False,
            "deletion_recommendation": False,
            "absence_is_not_proof_of_nonuse": True,
        },
        "mass": {
            "start": {
                "machinery_lines": start["machinery_lines"],
                "machinery_share": start["machinery_share"],
                "product_lines": start["product_lines"],
                "product_share": start["product_share"],
            },
            "current": {
                "machinery_lines": current["machinery_lines"],
                "machinery_share": current["machinery_share"],
                "product_lines": current["product_lines"],
                "product_share": current["product_share"],
            },
            "delta": {
                "machinery_lines": current["machinery_lines"] - start["machinery_lines"],
                "machinery_share": current["machinery_share"] - start["machinery_share"],
                "product_lines": current["product_lines"] - start["product_lines"],
                "product_share": current["product_share"] - start["product_share"],
            },
        },
        "status_counts": dict(sorted(status_counts.items())),
        "frames": frames,
        "files": files,
        "notes": [
            "A falling machinery percentage does not imply machinery shrank; inspect absolute machinery_lines alongside share.",
            "Dormancy and orphan labels are bounded evidence classes, not deletion instructions.",
            "No observed use inside the selected history window is not proof that a file is unused outside that window or by external consumers.",
        ],
    }
