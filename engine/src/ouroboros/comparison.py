from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .anatomy import fingerprint_from_payload


@dataclass(frozen=True, slots=True)
class ScanIdentity:
    analyzer_version: str | None
    analyzer_source_sha: str | None
    target_sha: str | None
    canonical: bool | None
    repository: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analyzer_version": self.analyzer_version,
            "analyzer_source_sha": self.analyzer_source_sha,
            "target_sha": self.target_sha,
            "canonical": self.canonical,
            "repository": self.repository,
        }


def _scan_identity(payload: dict) -> ScanIdentity:
    analyzer = payload.get("analyzer") or {}
    analyzer_source = (
        analyzer.get("source_sha")
        or analyzer.get("source_head")
        or analyzer.get("source_revision")
        or analyzer.get("source_commit")
    )
    repository_value = payload.get("repository")
    repository: str | None
    target_sha: str | None = None
    if isinstance(repository_value, dict):
        repository = repository_value.get("name") or repository_value.get("path") or repository_value.get("repository")
        target_sha = repository_value.get("sha") or repository_value.get("git_sha")
    elif repository_value is None:
        repository = payload.get("repository_name")
    else:
        repository = str(repository_value)

    repository_identity = payload.get("repository_identity") or {}
    target_sha = (
        target_sha
        or repository_identity.get("git_sha")
        or payload.get("repository_sha")
        or payload.get("target_sha")
    )
    scan = payload.get("scan") or {}
    canonical = scan.get("canonical") if "canonical" in scan else payload.get("canonical")
    return ScanIdentity(
        analyzer_version=analyzer.get("version"),
        analyzer_source_sha=analyzer_source,
        target_sha=target_sha,
        canonical=canonical if isinstance(canonical, bool) else None,
        repository=repository,
    )


def _metrics(payload: dict) -> tuple[dict, dict]:
    baseline = payload.get("baseline") or {}
    metrics = baseline.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("scan is missing baseline.metrics")
    semantic = payload.get("semantic") or {}
    semantic_metrics = semantic.get("metrics") or {}
    if not isinstance(semantic_metrics, dict):
        semantic_metrics = {}
    return metrics, semantic_metrics


def _profiles(payload: dict) -> dict[str, dict]:
    baseline = payload.get("baseline") or {}
    result: dict[str, dict] = {}
    for profile in baseline.get("directory_profiles") or []:
        if isinstance(profile, dict) and "path" in profile:
            result[str(profile["path"])] = profile
    return result


def _inversions(payload: dict) -> set[str]:
    result = set()
    for path, profile in _profiles(payload).items():
        product = int(profile.get("product_lines") or 0)
        machinery = int(profile.get("machinery_lines") or 0)
        if profile.get("is_inversion") is True or (product > 0 and machinery > product):
            result.add(path)
    return result


def _chain_summary(chain: dict) -> dict:
    symbol_ids = tuple(str(item) for item in chain.get("symbol_ids") or [])
    categories = tuple(str(item) for item in chain.get("categories") or [])
    relationships = tuple(str(item) for item in chain.get("relationships") or [])
    depth = int(chain.get("depth") if chain.get("depth") is not None else max(0, len(symbol_ids) - 1))
    return {
        "symbol_ids": list(symbol_ids),
        "categories": list(categories),
        "relationships": list(relationships),
        "depth": depth,
        "signature": " -> ".join(symbol_ids),
        "start": symbol_ids[0] if symbol_ids else None,
        "end": symbol_ids[-1] if symbol_ids else None,
    }


def _chains(payload: dict) -> list[dict]:
    semantic = payload.get("semantic") or {}
    chains = [_chain_summary(chain) for chain in (semantic.get("chains") or []) if isinstance(chain, dict)]
    if not chains:
        return []
    max_depth = max(chain["depth"] for chain in chains)
    return sorted((chain for chain in chains if chain["depth"] == max_depth), key=lambda chain: chain["signature"])


def _chain_changes(before: dict, after: dict) -> dict:
    before_chains = _chains(before)
    after_chains = _chains(after)
    before_by_signature = {chain["signature"]: chain for chain in before_chains}
    after_by_signature = {chain["signature"]: chain for chain in after_chains}
    added = [after_by_signature[key] for key in sorted(after_by_signature.keys() - before_by_signature.keys())]
    removed = [before_by_signature[key] for key in sorted(before_by_signature.keys() - after_by_signature.keys())]

    changed: list[dict] = []
    removed_by_endpoints: dict[tuple[str | None, str | None], list[dict]] = {}
    for chain in removed:
        removed_by_endpoints.setdefault((chain["start"], chain["end"]), []).append(chain)
    kept_added: list[dict] = []
    removed_signatures_used: set[str] = set()
    for chain in added:
        candidates = removed_by_endpoints.get((chain["start"], chain["end"]), [])
        candidate = next((item for item in candidates if item["signature"] not in removed_signatures_used), None)
        if candidate is None:
            kept_added.append(chain)
            continue
        removed_signatures_used.add(candidate["signature"])
        changed.append({"before": candidate, "after": chain})
    kept_removed = [chain for chain in removed if chain["signature"] not in removed_signatures_used]
    return {"added": kept_added, "removed": kept_removed, "changed": changed}


def _numeric_delta(before: float | int | None, after: float | int | None) -> float | None:
    if before is None or after is None:
        return None
    return float(after) - float(before)


def _coverage(metrics: dict) -> float | None:
    relationships = int(metrics.get("relationship_count") or 0)
    if relationships <= 0:
        return None
    value = metrics.get("exact_resolution_rate")
    return None if value is None else float(value)


def compare_scans(before: dict, after: dict) -> dict:
    before_metrics, before_semantic = _metrics(before)
    after_metrics, after_semantic = _metrics(after)
    before_identity = _scan_identity(before)
    after_identity = _scan_identity(after)

    before_counts = before_metrics.get("category_code_lines") or {}
    after_counts = after_metrics.get("category_code_lines") or {}
    categories = sorted(set(before_counts) | set(after_counts))
    category_deltas = {
        category: {
            "before": int(before_counts.get(category) or 0),
            "after": int(after_counts.get(category) or 0),
            "delta": int(after_counts.get(category) or 0) - int(before_counts.get(category) or 0),
        }
        for category in categories
    }

    before_profiles = _profiles(before)
    after_profiles = _profiles(after)
    crossovers = []
    for path in sorted(before_profiles.keys() & after_profiles.keys()):
        left = before_profiles[path]
        right = after_profiles[path]
        left_product = int(left.get("product_lines") or 0)
        left_machinery = int(left.get("machinery_lines") or 0)
        right_product = int(right.get("product_lines") or 0)
        right_machinery = int(right.get("machinery_lines") or 0)
        if left_product > left_machinery and right_machinery > right_product:
            crossovers.append(
                {
                    "path": path,
                    "before": {"product_lines": left_product, "machinery_lines": left_machinery},
                    "after": {"product_lines": right_product, "machinery_lines": right_machinery},
                }
            )

    before_inversions = _inversions(before)
    after_inversions = _inversions(after)
    analyzer_version_changed = before_identity.analyzer_version != after_identity.analyzer_version
    analyzer_source_changed = bool(
        before_identity.analyzer_source_sha
        and after_identity.analyzer_source_sha
        and before_identity.analyzer_source_sha != after_identity.analyzer_source_sha
    )
    canonical_setting_changed = bool(
        before_identity.canonical is not None
        and after_identity.canonical is not None
        and before_identity.canonical != after_identity.canonical
    )
    target_sha_changed = bool(
        before_identity.target_sha
        and after_identity.target_sha
        and before_identity.target_sha != after_identity.target_sha
    )
    like_for_like = not (analyzer_version_changed or analyzer_source_changed or canonical_setting_changed)

    before_exact = _coverage(before_semantic)
    after_exact = _coverage(after_semantic)
    before_scaffold = before_metrics.get("scaffolding_ratio")
    after_scaffold = after_metrics.get("scaffolding_ratio")
    comparison = {
        "schema": {"name": "ouroboros-comparison", "version": 1},
        "identity": {"before": before_identity.to_dict(), "after": after_identity.to_dict()},
        "measurement": {
            "analyzer_version_changed": analyzer_version_changed,
            "analyzer_source_changed": analyzer_source_changed,
            "canonical_setting_changed": canonical_setting_changed,
            "target_sha_changed": target_sha_changed,
            "like_for_like_analyzer": like_for_like,
        },
        "metrics": {
            "product_share": {
                "before": float(before_metrics.get("direct_product_share") or 0.0),
                "after": float(after_metrics.get("direct_product_share") or 0.0),
            },
            "machinery_share": {
                "before": float(before_metrics.get("tooling_share") or 0.0),
                "after": float(after_metrics.get("tooling_share") or 0.0),
            },
            "scaffolding_ratio": {
                "before": before_scaffold,
                "after": after_scaffold,
            },
            "recursive_depth": {
                "before": int(before_semantic.get("max_recursive_depth") or 0),
                "after": int(after_semantic.get("max_recursive_depth") or 0),
            },
            "semantic_index": {
                "before": float(before_semantic.get("semantic_ouroboros_index") or 0.0),
                "after": float(after_semantic.get("semantic_ouroboros_index") or 0.0),
            },
            "exact_coverage": {"before": before_exact, "after": after_exact},
        },
        "category_deltas": category_deltas,
        "inversion_hotspots": {
            "added": sorted(after_inversions - before_inversions),
            "removed": sorted(before_inversions - after_inversions),
        },
        "crossovers": crossovers,
        "deepest_exact_chains": _chain_changes(before, after),
        "fingerprints": {
            "before": before.get("fingerprint") or fingerprint_from_payload(before),
            "after": after.get("fingerprint") or fingerprint_from_payload(after),
        },
    }
    for metric in comparison["metrics"].values():
        metric["delta"] = _numeric_delta(metric["before"], metric["after"])
    comparison["structural_explanations"] = structural_explanations(comparison)
    return comparison


def structural_explanations(comparison: dict) -> list[str]:
    messages: list[str] = []
    for category, change in sorted(
        comparison.get("category_deltas", {}).items(),
        key=lambda item: (-abs(int(item[1].get("delta") or 0)), item[0]),
    ):
        delta = int(change.get("delta") or 0)
        if delta > 0:
            messages.append(f"{category.replace('-', ' ').title()} gained {delta:,} LOC.")
        elif delta < 0:
            messages.append(f"{category.replace('-', ' ').title()} lost {abs(delta):,} LOC.")
    for crossover in comparison.get("crossovers") or []:
        messages.append(f"{crossover['path']} crossed from product-dominant to machinery-dominant.")

    depth = comparison.get("metrics", {}).get("recursive_depth", {})
    delta = depth.get("delta")
    if delta is not None and delta > 0:
        messages.append(f"Max exact recursive depth increased from {depth['before']} to {depth['after']}.")
    elif delta is not None and delta < 0:
        messages.append(f"Max exact recursive depth decreased from {depth['before']} to {depth['after']}.")

    chains = comparison.get("deepest_exact_chains") or {}
    if chains.get("added"):
        chain = chains["added"][0]
        messages.append(f"A new deepest exact machinery chain appeared through {chain['signature']}.")
    if chains.get("removed"):
        chain = chains["removed"][0]
        messages.append(f"A previously deepest exact machinery chain disappeared: {chain['signature']}.")
    if chains.get("changed"):
        messages.append("A deepest exact chain kept the same endpoints but changed its internal structural path.")
    return messages
