from __future__ import annotations

import math
import re
from typing import Any, Iterable

from .neighbors import (
    MEASUREMENT_MODEL,
    NeighborError,
    fingerprint_from_index_record,
    fingerprint_from_scan,
)


_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.|$)")
_METRICS = (
    ("product_share", "Direct product share", "direct_product_share"),
    ("machinery_share", "Machinery share", "machinery_share"),
    ("scaffolding_ratio", "Scaffolding / product ratio", "scaffolding_ratio"),
    ("recursive_depth", "Exact recursive depth", "recursive_depth"),
    ("semantic_index", "Semantic Index", "semantic_index"),
    ("far_from_value", "Far-from-value symbol share", "far_from_value_symbol_share"),
    ("exact_coverage", "Exact relationship coverage", "exact_coverage"),
)


class ContextError(ValueError):
    pass


def semantic_model_for_version(version: str | None) -> str | None:
    if not version:
        return None
    match = _VERSION_RE.match(version)
    if not match:
        return None
    major, minor = int(match.group(1)), int(match.group(2))
    if major == 0 and 3 <= minor <= 10:
        return MEASUREMENT_MODEL
    return None


def _fingerprint(record: dict[str, Any], *, index_record: bool) -> dict[str, Any]:
    try:
        result = fingerprint_from_index_record(record) if index_record else fingerprint_from_scan(record)
    except NeighborError as exc:
        raise ContextError(str(exc)) from exc
    if result.get("measurement_model") is None:
        result["measurement_model"] = semantic_model_for_version(result.get("analyzer_version"))
    return result


def fingerprint_from_context_record(record: dict[str, Any]) -> dict[str, Any]:
    return _fingerprint(record, index_record=True)


def fingerprint_from_context_scan(record: dict[str, Any]) -> dict[str, Any]:
    return _fingerprint(record, index_record=False)


def _latest_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    newest: dict[str, dict[str, Any]] = {}
    for row in records:
        repo = row.get("repository")
        if not isinstance(repo, dict) or not repo.get("name"):
            continue
        key = str(repo["name"]).lower()
        current = newest.get(key)
        if current is None or str(row.get("scanned_at") or "") >= str(current.get("scanned_at") or ""):
            newest[key] = row
    return [newest[key] for key in sorted(newest)]


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _percentile(value: float, cohort: list[float]) -> float:
    below = sum(item < value for item in cohort)
    equal = sum(item == value for item in cohort)
    return 100.0 * (below + 0.5 * equal) / len(cohort)


def _band(percentile: float) -> str:
    if percentile < 10.0:
        return "lower-tail"
    if percentile > 90.0:
        return "upper-tail"
    return "middle-range"


def structural_context(query: dict[str, Any], records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    query_model = query.get("measurement_model")
    if not query_model:
        raise ContextError("Query measurement model is unknown; structural context would not be like-for-like")
    query_canonical = bool(query.get("canonical"))
    peers = []
    excluded = {"invalid": 0, "measurement_mismatch": 0}
    for row in _latest_records(records):
        try:
            fingerprint = fingerprint_from_context_record(row)
        except ContextError:
            excluded["invalid"] += 1
            continue
        if fingerprint.get("measurement_model") != query_model or bool(fingerprint.get("canonical")) != query_canonical:
            excluded["measurement_mismatch"] += 1
            continue
        peers.append(fingerprint)
    if not peers:
        raise ContextError("No comparable repository measurements were available in the corpus")

    dimensions: dict[str, Any] = {}
    for key, label, source_key in _METRICS:
        query_value = _finite(query.get(source_key))
        if query_value is None:
            dimensions[key] = {"label": label, "available": False, "reason": "query evidence unavailable"}
            continue
        cohort = []
        for peer in peers:
            value = _finite(peer.get(source_key))
            if value is not None:
                cohort.append(value)
        if not cohort:
            dimensions[key] = {"label": label, "available": False, "reason": "cohort evidence unavailable"}
            continue
        percentile = _percentile(query_value, cohort)
        dimensions[key] = {
            "label": label,
            "available": True,
            "value": query_value,
            "percentile": percentile,
            "band": _band(percentile),
            "cohort_size": len(cohort),
            "minimum": min(cohort),
            "median": sorted(cohort)[len(cohort) // 2],
            "maximum": max(cohort),
        }

    return {
        "schema": {"name": "ouroboros-structural-context", "version": 1},
        "measurement_model": query_model,
        "query": query,
        "cohort": {
            "repositories": len(peers),
            "records_deduped_by_repository": True,
            "canonical": query_canonical,
            "excluded": excluded,
        },
        "dimensions": dimensions,
        "semantics": {
            "percentile": "empirical relative position among comparable repositories; not a quality rank",
            "bands": {"lower-tail": "below the 10th percentile", "middle-range": "10th through 90th percentile", "upper-tail": "above the 90th percentile"},
            "judgment": "none; lower and upper positions can both be intentional",
        },
    }
