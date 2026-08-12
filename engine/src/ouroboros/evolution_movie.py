from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .anatomy import anatomy_fingerprint, spatial_layout
from .cli import scan
from .history import (
    DEFAULT_MAX_COMMITS,
    HistoryError,
    archive_commit,
    checkpoint_from_scan,
    commit_metadata,
    first_parent_commits,
    history_events,
    repository_root,
)


def _analyzer_source_sha() -> str | None:
    value = (os.environ.get("OUROBOROS_ANALYZER_SOURCE_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value):
        return value.lower()
    return None


def _scan_payload(root: Path, sha: str, snapshot: Path) -> tuple[dict[str, Any], Any, Any, dict[str, int]]:
    baseline, semantic = scan(snapshot, use_repo_config=False)
    payload = {
        "schema": {"name": "ouroboros-scan", "version": 2},
        "analyzer": {"name": "Ouroboros", "version": __version__, "source_sha": _analyzer_source_sha()},
        "repository": str(root),
        "repository_identity": {"git_sha": sha},
        "scan": {
            "canonical": True,
            "target_execution": False,
            "relationship_topology": "exact-only",
            "history_transport": "git-archive",
        },
        "fingerprint": anatomy_fingerprint(baseline, semantic),
        "baseline": baseline.to_dict(),
        "semantic": semantic.to_dict(),
    }
    diagnostics = {
        "warnings": len(baseline.warnings),
        "semantic_diagnostics": len(semantic.diagnostics),
    }
    return payload, baseline, semantic, diagnostics


def _file_rows(layout: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row["path"]): row
        for row in layout
        if isinstance(row, dict) and row.get("kind") == "file" and row.get("path")
    }


def layout_delta(before_layout: list[dict[str, Any]], after_layout: list[dict[str, Any]]) -> dict[str, Any]:
    before = _file_rows(before_layout)
    after = _file_rows(after_layout)
    summary = {
        "appeared": 0,
        "disappeared": 0,
        "classification_changed": 0,
        "grew": 0,
        "shrunk": 0,
        "value_distance_changed": 0,
    }
    changes: list[dict[str, Any]] = []

    for path in sorted(set(before) | set(after)):
        left = before.get(path)
        right = after.get(path)
        appeared = left is None
        disappeared = right is None
        before_weight = 0 if left is None else int(left.get("weight") or 0)
        after_weight = 0 if right is None else int(right.get("weight") or 0)
        before_category = None if left is None else left.get("category")
        after_category = None if right is None else right.get("category")
        before_distance = None if left is None else left.get("value_distance")
        after_distance = None if right is None else right.get("value_distance")
        weight_delta = after_weight - before_weight
        classification_changed = left is not None and right is not None and before_category != after_category
        value_distance_changed = left is not None and right is not None and before_distance != after_distance
        grew = left is not None and right is not None and weight_delta > 0
        shrunk = left is not None and right is not None and weight_delta < 0

        if appeared:
            summary["appeared"] += 1
        if disappeared:
            summary["disappeared"] += 1
        if classification_changed:
            summary["classification_changed"] += 1
        if grew:
            summary["grew"] += 1
        if shrunk:
            summary["shrunk"] += 1
        if value_distance_changed:
            summary["value_distance_changed"] += 1

        if appeared or disappeared or classification_changed or grew or shrunk or value_distance_changed:
            changes.append(
                {
                    "path": path,
                    "appeared": appeared,
                    "disappeared": disappeared,
                    "classification_changed": classification_changed,
                    "grew": grew,
                    "shrunk": shrunk,
                    "value_distance_changed": value_distance_changed,
                    "before_weight": before_weight,
                    "after_weight": after_weight,
                    "weight_delta": weight_delta,
                    "before_category": before_category,
                    "after_category": after_category,
                    "before_value_distance": before_distance,
                    "after_value_distance": after_distance,
                }
            )

    changes.sort(
        key=lambda row: (
            -int(row["appeared"] or row["disappeared"]),
            -abs(int(row["weight_delta"])),
            -int(row["classification_changed"]),
            str(row["path"]),
        )
    )
    return {"baseline_frame": False, "summary": summary, "changes": changes}


def _baseline_delta() -> dict[str, Any]:
    return {
        "baseline_frame": True,
        "summary": {
            "appeared": 0,
            "disappeared": 0,
            "classification_changed": 0,
            "grew": 0,
            "shrunk": 0,
            "value_distance_changed": 0,
        },
        "changes": [],
    }


def scan_evolution_movie(
    path: str | Path,
    *,
    from_ref: str,
    to_ref: str = "HEAD",
    max_commits: int = DEFAULT_MAX_COMMITS,
) -> dict[str, Any]:
    root = repository_root(path)
    commits = first_parent_commits(root, from_ref, to_ref, max_commits=max_commits)
    frames: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    previous_payload: dict[str, Any] | None = None
    previous_meta: dict[str, str] | None = None
    previous_layout: list[dict[str, Any]] | None = None

    with tempfile.TemporaryDirectory(prefix="ouroboros-movie-") as temp:
        temp_root = Path(temp)
        for index, sha in enumerate(commits):
            commit_dir = temp_root / f"commit-{index:04d}"
            snapshot = commit_dir / "snapshot"
            acquisition = archive_commit(root, sha, snapshot)
            payload, baseline, semantic, diagnostics = _scan_payload(root, sha, snapshot)
            metadata = commit_metadata(root, sha)
            checkpoint = checkpoint_from_scan(metadata, payload, acquisition, diagnostics)
            layout = [rect.to_dict() for rect in spatial_layout(baseline)]
            delta = _baseline_delta() if previous_layout is None else layout_delta(previous_layout, layout)
            frames.append(
                {
                    **checkpoint,
                    "frame_index": index,
                    "map": {
                        "width": 1000.0,
                        "height": 620.0,
                        "file_count": sum(1 for row in layout if row["kind"] == "file"),
                        "directory_count": sum(1 for row in layout if row["kind"] == "directory"),
                        "rectangles": layout,
                    },
                    "delta": delta,
                }
            )

            if previous_payload is not None and previous_meta is not None:
                events.extend(history_events(previous_payload, payload, previous_meta, metadata))

            previous_payload = payload
            previous_meta = metadata
            previous_layout = layout
            shutil.rmtree(commit_dir, ignore_errors=True)

    return {
        "schema": {"name": "ouroboros-evolution-movie", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": __version__, "source_sha": _analyzer_source_sha()},
        "repository": str(root),
        "range": {
            "from_ref": from_ref,
            "from_sha": commits[0],
            "to_ref": to_ref,
            "to_sha": commits[-1],
            "commits_scanned": len(commits),
            "max_commits": max_commits,
            "first_parent": True,
            "sampled": False,
        },
        "movie_policy": {
            "canonical": True,
            "target_execution": False,
            "network_access": False,
            "history_transport": "git-archive",
            "every_commit_in_range_scanned": True,
            "layout": "deterministic anatomy spatial_layout",
            "quality_judgment": False,
        },
        "frames": frames,
        "events": events,
    }


def write_evolution_movie_json(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return destination.resolve()
