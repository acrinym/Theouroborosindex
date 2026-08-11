from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StoryError(ValueError):
    pass


def load_object(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StoryError(f"Could not read {target}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise StoryError(f"{target} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise StoryError(f"{target} must contain a JSON object")
    return value


def _schema_name(payload: dict[str, Any]) -> str | None:
    schema = payload.get("schema")
    if isinstance(schema, dict) and isinstance(schema.get("name"), str):
        return schema["name"]
    if isinstance(schema, str):
        return schema.split("/", 1)[0]
    return None


def _require_schema(payload: dict[str, Any], expected: str, label: str) -> None:
    observed = _schema_name(payload)
    if observed != expected:
        shown = observed or "missing"
        raise StoryError(f"{label} has schema {shown!r}; expected {expected!r}")


def _scan_sha(scan: dict[str, Any]) -> str | None:
    identity = scan.get("repository_identity")
    if isinstance(identity, dict) and isinstance(identity.get("git_sha"), str):
        return identity["git_sha"]
    value = scan.get("repository_sha")
    return value if isinstance(value, str) else None


def compose_story(
    scan: dict[str, Any],
    *,
    history: dict[str, Any] | None = None,
    drivers: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_schema(scan, "ouroboros-scan", "Current scan")
    if history is not None:
        _require_schema(history, "ouroboros-history", "Bounded History artifact")
    if drivers is not None:
        _require_schema(drivers, "ouroboros-change-drivers", "Change Drivers artifact")
    if context is not None:
        _require_schema(context, "ouroboros-structural-context", "Structural Context artifact")

    baseline = scan.get("baseline")
    semantic = scan.get("semantic")
    if not isinstance(baseline, dict) or not isinstance(semantic, dict):
        raise StoryError("Current scan is missing baseline or semantic analysis")
    bm = baseline.get("metrics")
    sm = semantic.get("metrics")
    if not isinstance(bm, dict) or not isinstance(sm, dict):
        raise StoryError("Current scan is missing baseline.metrics or semantic.metrics")

    current_sha = _scan_sha(scan)
    warnings: list[str] = []
    if history is not None:
        history_to = ((history.get("range") or {}).get("to_sha"))
        if current_sha and history_to and current_sha != history_to:
            warnings.append("The history range ends at a different commit than the current scan.")
    if context is not None:
        context_sha = ((context.get("query") or {}).get("repository_sha"))
        if current_sha and context_sha and current_sha != context_sha:
            warnings.append("The structural-context query is for a different commit than the current scan.")

    driver_relation = None
    if drivers is not None:
        after_sha = ((drivers.get("after") or {}).get("sha"))
        if current_sha and after_sha:
            driver_relation = "current-commit" if current_sha == after_sha else "historical-change-point"

    relationship_count = int(sm.get("relationship_count") or 0)
    exact_coverage = float(sm.get("exact_resolution_rate") or 0.0) if relationship_count else None
    return {
        "schema": {"name": "ouroboros-anatomy-story", "version": 1},
        "repository": scan.get("repository"),
        "current": {
            "sha": current_sha,
            "product_share": float(bm.get("direct_product_share") or 0.0),
            "machinery_share": float(bm.get("tooling_share") or 0.0),
            "scaffolding_ratio": bm.get("scaffolding_ratio"),
            "recursive_depth": int(sm.get("max_recursive_depth") or 0),
            "semantic_index": float(sm.get("semantic_ouroboros_index") or 0.0),
            "exact_coverage": exact_coverage,
            "fingerprint": scan.get("fingerprint") or {},
        },
        "history": history,
        "drivers": drivers,
        "driver_relation": driver_relation,
        "context": context,
        "coherence": {
            "warnings": warnings,
            "current_history_match": not any("history range" in warning for warning in warnings),
            "current_context_match": not any("structural-context" in warning for warning in warnings),
        },
        "sources": {
            "current_scan": True,
            "bounded_history": history is not None,
            "change_drivers": drivers is not None,
            "structural_context": context is not None,
        },
        "semantics": "one deterministic presentation of existing Ouroboros evidence; it adds no new score, policy verdict, or inferred causality",
    }
