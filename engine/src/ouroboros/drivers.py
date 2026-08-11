from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .comparison import compare_scans


DEFAULT_DRIVER_LIMIT = 8


def _components(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    baseline = payload.get("baseline") or {}
    rows = baseline.get("components") or []
    return {
        str(row["path"]): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }


def _file_driver(path: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    before_lines = int((before or {}).get("code_lines") or 0)
    after_lines = int((after or {}).get("code_lines") or 0)
    before_category = (before or {}).get("category")
    after_category = (after or {}).get("category")
    if before is None:
        status = "added"
    elif after is None:
        status = "removed"
    elif before_category != after_category:
        status = "recategorized"
    else:
        status = "changed"
    moved_lines = max(before_lines, after_lines) if before_category != after_category else abs(after_lines - before_lines)
    return {
        "path": path,
        "status": status,
        "before_category": before_category,
        "after_category": after_category,
        "before_code_lines": before_lines,
        "after_code_lines": after_lines,
        "delta_code_lines": after_lines - before_lines,
        "structural_movement_lines": moved_lines,
    }


def change_drivers(before: dict[str, Any], after: dict[str, Any], *, limit: int = DEFAULT_DRIVER_LIMIT) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("driver limit must be at least 1")
    comparison = compare_scans(before, after)
    before_components = _components(before)
    after_components = _components(after)
    files: list[dict[str, Any]] = []
    for path in sorted(set(before_components) | set(after_components)):
        driver = _file_driver(path, before_components.get(path), after_components.get(path))
        if driver["structural_movement_lines"] > 0 or driver["status"] in {"added", "removed", "recategorized"}:
            files.append(driver)
    files.sort(key=lambda row: (-int(row["structural_movement_lines"]), row["path"]))

    categories = []
    for category, row in (comparison.get("category_deltas") or {}).items():
        delta = int(row.get("delta") or 0)
        if delta:
            categories.append(
                {
                    "category": category,
                    "before": int(row.get("before") or 0),
                    "after": int(row.get("after") or 0),
                    "delta": delta,
                }
            )
    categories.sort(key=lambda row: (-abs(int(row["delta"])), row["category"]))

    return {
        "semantics": "largest observed adjacent structural contributors; evidence, not blame or a quality score",
        "files": files[:limit],
        "file_changes_observed": len(files),
        "categories": categories,
        "deepest_exact_chains": comparison.get("deepest_exact_chains") or {"added": [], "removed": [], "changed": []},
        "structural_explanations": comparison.get("structural_explanations") or [],
    }


def scan_change_drivers(
    path: str | Path,
    *,
    before_ref: str,
    after_ref: str,
    limit: int = DEFAULT_DRIVER_LIMIT,
) -> dict[str, Any]:
    from .history import _scan_payload, archive_commit, commit_metadata, repository_root, resolve_commit

    root = repository_root(path)
    before_sha = resolve_commit(root, before_ref)
    after_sha = resolve_commit(root, after_ref)
    payloads: list[dict[str, Any]] = []
    acquisitions: list[dict[str, int]] = []
    with tempfile.TemporaryDirectory(prefix="ouroboros-drivers-") as temp:
        temp_root = Path(temp)
        for index, sha in enumerate((before_sha, after_sha)):
            commit_dir = temp_root / f"snapshot-{index}"
            snapshot = commit_dir / "tree"
            acquisitions.append(archive_commit(root, sha, snapshot))
            payload, _ = _scan_payload(root, sha, snapshot)
            payloads.append(payload)
            shutil.rmtree(commit_dir, ignore_errors=True)

    return {
        "schema": {"name": "ouroboros-change-drivers", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": __version__},
        "repository": str(root),
        "before": {**commit_metadata(root, before_sha), "ref": before_ref, "acquisition": acquisitions[0]},
        "after": {**commit_metadata(root, after_sha), "ref": after_ref, "acquisition": acquisitions[1]},
        "scan_policy": {
            "canonical": True,
            "target_execution": False,
            "history_transport": "git-archive",
            "snapshots_scanned": 2,
        },
        "drivers": change_drivers(payloads[0], payloads[1], limit=limit),
    }
