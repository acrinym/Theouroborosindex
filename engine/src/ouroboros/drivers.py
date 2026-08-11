from __future__ import annotations

from typing import Any

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
    """Return bounded, inspectable structural contributors between two scans."""
    if limit < 1:
        raise ValueError("driver limit must be at least 1")
    comparison = compare_scans(before, after)
    before_components = _components(before)
    after_components = _components(after)
    files: list[dict[str, Any]] = []
    for path in sorted(set(before_components) | set(after_components)):
        left = before_components.get(path)
        right = after_components.get(path)
        driver = _file_driver(path, left, right)
        if driver["structural_movement_lines"] > 0 or driver["status"] in {"added", "removed", "recategorized"}:
            files.append(driver)
    files.sort(key=lambda row: (-int(row["structural_movement_lines"]), row["path"]))

    category_rows = []
    for category, row in (comparison.get("category_deltas") or {}).items():
        delta = int(row.get("delta") or 0)
        if delta:
            category_rows.append(
                {
                    "category": category,
                    "before": int(row.get("before") or 0),
                    "after": int(row.get("after") or 0),
                    "delta": delta,
                }
            )
    category_rows.sort(key=lambda row: (-abs(int(row["delta"])), row["category"]))

    return {
        "semantics": "largest observed adjacent structural contributors; evidence, not blame or a quality score",
        "files": files[:limit],
        "file_changes_observed": len(files),
        "categories": category_rows,
        "deepest_exact_chains": comparison.get("deepest_exact_chains") or {"added": [], "removed": [], "changed": []},
    }


def focus_directory_drivers(drivers: dict[str, Any], directory: str, *, limit: int = DEFAULT_DRIVER_LIMIT) -> list[dict[str, Any]]:
    prefix = directory.rstrip("/") + "/" if directory not in {"", "."} else ""
    rows = [row for row in drivers.get("files") or [] if str(row.get("path") or "").startswith(prefix)]
    return rows[:limit]
