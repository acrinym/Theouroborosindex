from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .model import Category


MEASUREMENT_MODEL = "ouroboros-semantic-v1"
CATEGORY_ORDER = tuple(category.value for category in Category)

_GROUP_WEIGHTS = {
    "code_composition": 0.40,
    "symbol_composition": 0.20,
    "recursive_depth": 0.15,
    "semantic_index": 0.10,
    "far_from_value": 0.10,
    "exact_coverage": 0.05,
}
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.|$)")


class NeighborError(ValueError):
    pass


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return default


def _optional_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _clean_counts(counts: Any) -> dict[str, float]:
    if not isinstance(counts, dict):
        counts = {}
    return {category: max(0.0, _number(counts.get(category))) for category in CATEGORY_ORDER}


def _share_map(counts: Any) -> tuple[dict[str, float], float]:
    clean = _clean_counts(counts)
    total = sum(clean.values())
    if total <= 0:
        return ({category: 0.0 for category in CATEGORY_ORDER}, 0.0)
    return ({category: clean[category] / total for category in CATEGORY_ORDER}, total)


def _semantic_model_for_version(version: str | None) -> str | None:
    if not version:
        return None
    match = _VERSION_RE.match(version)
    if not match:
        return None
    major = int(match.group(1))
    minor = int(match.group(2))
    # This compatibility declaration is deliberately closed-ended. A future
    # release must explicitly opt in if its measurement rules remain equivalent.
    if major == 0 and 3 <= minor <= 7:
        return MEASUREMENT_MODEL
    return None


def _record_identity(record: dict[str, Any]) -> tuple[str, str | None]:
    repository = record.get("repository")
    if isinstance(repository, dict):
        name = repository.get("name")
        sha = repository.get("sha")
        return (str(name or "<unknown>"), str(sha) if isinstance(sha, str) else None)
    name = record.get("repository_name") or record.get("repository") or "<scan>"
    identity = record.get("repository_identity")
    sha = identity.get("git_sha") if isinstance(identity, dict) else record.get("repository_sha")
    return (str(name), str(sha) if isinstance(sha, str) else None)


def fingerprint_from_index_record(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("status") != "ok":
        raise NeighborError("Index record is not a successful scan")
    measurement = record.get("measurement")
    if not isinstance(measurement, dict):
        raise NeighborError("Index record has no measurement")
    baseline = measurement.get("baseline")
    semantic = measurement.get("semantic")
    if not isinstance(baseline, dict) or not isinstance(semantic, dict):
        raise NeighborError("Index measurement is missing baseline or semantic metrics")

    repository_name, repository_sha = _record_identity(record)
    analyzer = record.get("analyzer") if isinstance(record.get("analyzer"), dict) else {}
    version = str(analyzer.get("version") or "")
    relationship_count = int(max(0, _number(semantic.get("relationship_count"))))
    exact_coverage = _optional_number(semantic.get("exact_resolution_rate")) if relationship_count else None
    model = measurement.get("measurement_model") or _semantic_model_for_version(version)
    code_shares, code_total = _share_map(measurement.get("category_code_lines"))
    symbol_shares, symbol_total = _share_map(measurement.get("category_symbol_counts"))

    return {
        "repository_name": repository_name,
        "repository_sha": repository_sha,
        "analyzer_version": version or None,
        "analyzer_source_revision": analyzer.get("source_revision"),
        "canonical": bool(analyzer.get("canonical", True)),
        "measurement_model": model,
        "code_category_shares": code_shares,
        "code_line_total": int(code_total),
        "symbol_category_shares": symbol_shares,
        "symbol_count": int(symbol_total),
        "recursive_depth": int(max(0, _number(semantic.get("max_recursive_depth")))),
        "semantic_index": min(100.0, max(0.0, _number(semantic.get("semantic_ouroboros_index")))),
        "far_from_value_symbol_share": min(1.0, max(0.0, _number(semantic.get("far_from_value_symbol_share")))),
        "exact_coverage": exact_coverage,
        "relationship_count": relationship_count,
        "scaffolding_ratio": _optional_number(baseline.get("scaffolding_ratio")),
        "direct_product_share": min(1.0, max(0.0, _number(baseline.get("direct_product_share")))),
        "machinery_share": min(1.0, max(0.0, _number(baseline.get("tooling_share")))),
    }


def fingerprint_from_scan(record: dict[str, Any]) -> dict[str, Any]:
    baseline = record.get("baseline")
    semantic = record.get("semantic")
    if not isinstance(baseline, dict) or not isinstance(semantic, dict):
        raise NeighborError("Scan JSON is missing baseline or semantic results")
    baseline_metrics = baseline.get("metrics")
    semantic_metrics = semantic.get("metrics")
    if not isinstance(baseline_metrics, dict) or not isinstance(semantic_metrics, dict):
        raise NeighborError("Scan JSON is missing metrics")

    symbol_counts: Counter[str] = Counter()
    symbols = semantic.get("symbols")
    if isinstance(symbols, list):
        for symbol in symbols:
            if isinstance(symbol, dict) and isinstance(symbol.get("category"), str):
                symbol_counts[symbol["category"]] += 1

    repository_name, repository_sha = _record_identity(record)
    analyzer = record.get("analyzer") if isinstance(record.get("analyzer"), dict) else {}
    scan = record.get("scan") if isinstance(record.get("scan"), dict) else {}
    version = str(analyzer.get("version") or "")
    relationship_count = int(max(0, _number(semantic_metrics.get("relationship_count"))))
    exact_coverage = _optional_number(semantic_metrics.get("exact_resolution_rate")) if relationship_count else None
    model = scan.get("measurement_model") or _semantic_model_for_version(version)
    code_shares, code_total = _share_map(baseline_metrics.get("category_code_lines"))
    symbol_shares, symbol_total = _share_map(symbol_counts)

    return {
        "repository_name": repository_name,
        "repository_sha": repository_sha,
        "analyzer_version": version or None,
        "analyzer_source_revision": analyzer.get("source_sha") or analyzer.get("source_revision"),
        "canonical": bool(scan.get("canonical", analyzer.get("canonical", False))),
        "measurement_model": model,
        "code_category_shares": code_shares,
        "code_line_total": int(code_total),
        "symbol_category_shares": symbol_shares,
        "symbol_count": int(symbol_total),
        "recursive_depth": int(max(0, _number(semantic_metrics.get("max_recursive_depth")))),
        "semantic_index": min(100.0, max(0.0, _number(semantic_metrics.get("semantic_ouroboros_index")))),
        "far_from_value_symbol_share": min(1.0, max(0.0, _number(semantic_metrics.get("far_from_value_symbol_share")))),
        "exact_coverage": exact_coverage,
        "relationship_count": relationship_count,
        "scaffolding_ratio": _optional_number(baseline_metrics.get("scaffolding_ratio")),
        "direct_product_share": min(1.0, max(0.0, _number(baseline_metrics.get("direct_product_share")))),
        "machinery_share": min(1.0, max(0.0, _number(baseline_metrics.get("tooling_share")))),
    }


def fingerprint_from_record(record: dict[str, Any]) -> dict[str, Any]:
    if "measurement" in record and "status" in record:
        return fingerprint_from_index_record(record)
    return fingerprint_from_scan(record)


def load_json(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise NeighborError(f"Could not read {target}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise NeighborError(f"{target} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise NeighborError(f"{target} must contain a JSON object")
    return payload


def load_corpus(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path).expanduser()
    rows: list[dict[str, Any]] = []
    try:
        with target.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise NeighborError(f"{target} has invalid JSON on line {line_number}") from exc
                if isinstance(row, dict) and row.get("status") == "ok" and isinstance(row.get("measurement"), dict):
                    rows.append(row)
    except OSError as exc:
        raise NeighborError(f"Could not read {target}: {exc}") from exc
    if not rows:
        raise NeighborError(f"{target} contains no successful Index records")
    return rows


def select_query_record(
    records: Iterable[dict[str, Any]],
    repository: str,
    *,
    sha: str | None = None,
) -> dict[str, Any]:
    repository_lower = repository.lower()
    matches = []
    for row in records:
        repo = row.get("repository")
        if not isinstance(repo, dict) or str(repo.get("name", "")).lower() != repository_lower:
            continue
        if sha is not None and str(repo.get("sha", "")).lower() != sha.lower():
            continue
        matches.append(row)
    if not matches:
        suffix = f"@{sha}" if sha else ""
        raise NeighborError(f"No successful Index record found for {repository}{suffix}")
    matches.sort(key=lambda row: str(row.get("scanned_at") or ""))
    return matches[-1]


def _composition_distance(left: dict[str, float], right: dict[str, float]) -> float:
    return min(1.0, 0.5 * sum(abs(left.get(category, 0.0) - right.get(category, 0.0)) for category in CATEGORY_ORDER))


def _depth_value(depth: int) -> float:
    depth = max(0, depth)
    return depth / (depth + 3.0)


def structural_distance(query: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    components: dict[str, dict[str, float]] = {}
    if int(query.get("code_line_total") or 0) > 0 and int(candidate.get("code_line_total") or 0) > 0:
        components["code_composition"] = {
            "distance": _composition_distance(query["code_category_shares"], candidate["code_category_shares"]),
            "weight": _GROUP_WEIGHTS["code_composition"],
        }
    if int(query.get("symbol_count") or 0) > 0 and int(candidate.get("symbol_count") or 0) > 0:
        components["symbol_composition"] = {
            "distance": _composition_distance(query["symbol_category_shares"], candidate["symbol_category_shares"]),
            "weight": _GROUP_WEIGHTS["symbol_composition"],
        }
    components.update(
        {
            "recursive_depth": {
                "distance": abs(_depth_value(query["recursive_depth"]) - _depth_value(candidate["recursive_depth"])),
                "weight": _GROUP_WEIGHTS["recursive_depth"],
            },
            "semantic_index": {
                "distance": abs(query["semantic_index"] - candidate["semantic_index"]) / 100.0,
                "weight": _GROUP_WEIGHTS["semantic_index"],
            },
            "far_from_value": {
                "distance": abs(query["far_from_value_symbol_share"] - candidate["far_from_value_symbol_share"]),
                "weight": _GROUP_WEIGHTS["far_from_value"],
            },
        }
    )
    if query.get("exact_coverage") is not None and candidate.get("exact_coverage") is not None:
        components["exact_coverage"] = {
            "distance": abs(float(query["exact_coverage"]) - float(candidate["exact_coverage"])),
            "weight": _GROUP_WEIGHTS["exact_coverage"],
        }

    weight_total = sum(component["weight"] for component in components.values())
    distance = 0.0
    for component in components.values():
        effective_weight = component["weight"] / weight_total if weight_total else 0.0
        component["effective_weight"] = effective_weight
        component["contribution"] = component["distance"] * effective_weight
        distance += component["contribution"]
    return {
        "distance": min(1.0, max(0.0, distance)),
        "components": components,
    }


def _category_differences(query: dict[str, Any], candidate: dict[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    rows = []
    for category in CATEGORY_ORDER:
        before = float(query["code_category_shares"].get(category, 0.0))
        after = float(candidate["code_category_shares"].get(category, 0.0))
        rows.append({"category": category, "query": before, "candidate": after, "delta": after - before})
    rows.sort(key=lambda row: (-abs(row["delta"]), row["category"]))
    return rows[:limit]


def _explanation(query: dict[str, Any], candidate: dict[str, Any], distance: dict[str, Any]) -> list[str]:
    components = distance["components"]
    lines: list[str] = []
    code = components.get("code_composition")
    symbols = components.get("symbol_composition")
    if code is not None:
        lines.append(f"Code-purpose composition distance is {code['distance']:.3f}.")
    else:
        lines.append("Code-purpose composition was unavailable for at least one scan and was excluded from distance weighting.")
    if symbols is not None:
        lines.append(f"Symbol-role composition distance is {symbols['distance']:.3f}.")
    else:
        lines.append("Symbol-role composition was unavailable for at least one scan and was excluded from distance weighting.")
    if query["recursive_depth"] == candidate["recursive_depth"]:
        lines.append(f"Both scans have exact recursive depth {query['recursive_depth']}.")
    else:
        lines.append(f"Exact recursive depth differs: {query['recursive_depth']} versus {candidate['recursive_depth']}.")
    index_delta = candidate["semantic_index"] - query["semantic_index"]
    lines.append(f"Semantic Index differs by {index_delta:+.1f} points; this is structural context, not a quality judgment.")
    if query.get("exact_coverage") is None or candidate.get("exact_coverage") is None:
        lines.append("Exact relationship coverage was unavailable for at least one scan and was excluded from distance weighting.")
    return lines


def find_neighbors(
    query: dict[str, Any],
    records: Iterable[dict[str, Any]],
    *,
    limit: int = 10,
    cross_model: bool = False,
    include_same_repository: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise NeighborError("limit must be at least 1")
    candidate_records: list[dict[str, Any]] = []
    excluded = Counter()
    query_name = str(query.get("repository_name") or "")
    query_sha = query.get("repository_sha")
    query_model = query.get("measurement_model")
    query_canonical = bool(query.get("canonical"))

    for row in records:
        try:
            candidate = fingerprint_from_index_record(row)
        except NeighborError:
            excluded["invalid_measurement"] += 1
            continue
        same_repository = candidate["repository_name"].lower() == query_name.lower()
        same_identity = same_repository and candidate.get("repository_sha") == query_sha
        if same_identity:
            excluded["same_identity"] += 1
            continue
        if not include_same_repository and same_repository:
            excluded["same_repository"] += 1
            continue
        same_model = bool(query_model and candidate.get("measurement_model") == query_model)
        same_canonical = candidate.get("canonical") == query_canonical
        if not cross_model and (not same_model or not same_canonical):
            excluded["measurement_model_mismatch"] += 1
            continue

        distance = structural_distance(query, candidate)
        candidate_records.append(
            {
                "repository_name": candidate["repository_name"],
                "repository_sha": candidate.get("repository_sha"),
                "analyzer_version": candidate.get("analyzer_version"),
                "measurement_model": candidate.get("measurement_model"),
                "canonical": candidate.get("canonical"),
                "comparable_measurement_model": same_model and same_canonical,
                "distance": distance["distance"],
                "components": distance["components"],
                "category_differences": _category_differences(query, candidate),
                "explanation": _explanation(query, candidate, distance),
                "fingerprint": candidate,
            }
        )

    candidate_records.sort(key=lambda row: (row["distance"], row["repository_name"], row.get("repository_sha") or ""))
    best_by_repository: dict[str, dict[str, Any]] = {}
    for candidate in candidate_records:
        key = candidate["repository_name"].lower()
        if key not in best_by_repository:
            best_by_repository[key] = candidate
    candidates = list(best_by_repository.values())
    candidates.sort(key=lambda row: (row["distance"], row["repository_name"], row.get("repository_sha") or ""))
    result = candidates[:limit]
    return {
        "schema": {"name": "ouroboros-neighborhood", "version": 1},
        "measurement_model": query_model,
        "query": query,
        "neighbors": result,
        "cohort": {
            "records_seen": sum(excluded.values()) + len(candidate_records),
            "eligible_records": len(candidate_records),
            "eligible": len(candidates),
            "eligible_repositories": len(candidates),
            "returned": len(result),
            "excluded": dict(sorted(excluded.items())),
            "cross_model_enabled": cross_model,
            "same_repository_enabled": include_same_repository,
        },
        "distance_semantics": {
            "range": [0.0, 1.0],
            "meaning": "lower means more similar repository anatomy; this is not a quality score",
            "group_weights": dict(_GROUP_WEIGHTS),
            "missing_evidence": "unavailable dimensions are excluded and remaining weights are renormalized",
        },
    }
