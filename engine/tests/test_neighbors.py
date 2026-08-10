from __future__ import annotations

import json
from pathlib import Path

from ouroboros.neighbors import (
    MEASUREMENT_MODEL,
    find_neighbors,
    fingerprint_from_index_record,
    fingerprint_from_scan,
    load_corpus,
    select_query_record,
    structural_distance,
)
from ouroboros.neighbors_cli import main as neighbors_main
from ouroboros.neighbors_report import build_neighbors_report_html


def _index_record(
    name: str,
    *,
    sha: str,
    version: str = "0.6.0",
    product: int = 70,
    testing: int = 20,
    tooling: int = 10,
    depth: int = 1,
    index: float = 10.0,
    exact: float = 0.8,
    relationships: int = 10,
    scanned_at: str = "2026-08-10T00:00:00Z",
) -> dict:
    total = product + testing + tooling
    return {
        "schema": "ouroboros-index-record/v1",
        "status": "ok",
        "scanned_at": scanned_at,
        "repository": {"name": name, "sha": sha, "id": abs(hash(name)) % 100000},
        "analyzer": {"name": "Ouroboros", "version": version, "source_revision": "a" * 40, "canonical": True},
        "measurement": {
            "baseline": {
                "direct_product_share": product / total,
                "tooling_share": (testing + tooling) / total,
                "scaffolding_ratio": (testing + tooling) / product,
            },
            "semantic": {
                "relationship_count": relationships,
                "exact_resolution_rate": exact,
                "max_recursive_depth": depth,
                "semantic_ouroboros_index": index,
                "far_from_value_symbol_share": 0.2,
            },
            "category_code_lines": {
                "core-product": product,
                "testing": testing,
                "developer-tooling": tooling,
            },
            "category_symbol_counts": {
                "core-product": product // 10,
                "testing": max(1, testing // 10),
                "developer-tooling": max(1, tooling // 10),
            },
        },
    }


def _scan(name: str = "/tmp/query") -> dict:
    return {
        "schema": {"name": "ouroboros-scan", "version": 2},
        "analyzer": {"name": "Ouroboros", "version": "0.6.0", "source_sha": "b" * 40},
        "repository": name,
        "repository_identity": {"git_sha": "f" * 40},
        "scan": {"canonical": True, "target_execution": False, "relationship_topology": "exact-only"},
        "baseline": {
            "metrics": {
                "direct_product_share": 0.7,
                "tooling_share": 0.3,
                "scaffolding_ratio": 3 / 7,
                "category_code_lines": {"core-product": 70, "testing": 20, "developer-tooling": 10},
            }
        },
        "semantic": {
            "metrics": {
                "relationship_count": 10,
                "exact_resolution_rate": 0.8,
                "max_recursive_depth": 1,
                "semantic_ouroboros_index": 10.0,
                "far_from_value_symbol_share": 0.2,
            },
            "symbols": [
                {"category": "core-product"},
                {"category": "core-product"},
                {"category": "testing"},
                {"category": "developer-tooling"},
            ],
        },
    }


def test_legacy_semantic_records_share_measurement_model():
    fingerprint = fingerprint_from_index_record(_index_record("org/repo", sha="1" * 40, version="0.4.0"))
    assert fingerprint["measurement_model"] == MEASUREMENT_MODEL


def test_structural_distance_is_zero_for_identical_anatomy_and_decomposed():
    query = fingerprint_from_index_record(_index_record("org/query", sha="1" * 40))
    peer = fingerprint_from_index_record(_index_record("org/peer", sha="2" * 40))
    result = structural_distance(query, peer)
    assert result["distance"] == 0.0
    assert set(result["components"]) == {
        "code_composition",
        "symbol_composition",
        "recursive_depth",
        "semantic_index",
        "far_from_value",
        "exact_coverage",
    }
    assert abs(sum(row["effective_weight"] for row in result["components"].values()) - 1.0) < 1e-9


def test_missing_exact_coverage_is_removed_and_weights_are_renormalized():
    query = fingerprint_from_index_record(_index_record("org/query", sha="1" * 40, relationships=0))
    peer = fingerprint_from_index_record(_index_record("org/peer", sha="2" * 40))
    result = structural_distance(query, peer)
    assert "exact_coverage" not in result["components"]
    assert abs(sum(row["effective_weight"] for row in result["components"].values()) - 1.0) < 1e-9


def test_neighbor_ranking_prefers_closer_anatomy_and_excludes_same_repo():
    query_record = _index_record("org/query", sha="1" * 40)
    query = fingerprint_from_index_record(query_record)
    close = _index_record("org/close", sha="2" * 40, product=68, testing=21, tooling=11, depth=1, index=11.0)
    far = _index_record("org/far", sha="3" * 40, product=20, testing=50, tooling=30, depth=5, index=60.0)
    same_repo = _index_record("org/query", sha="4" * 40, product=69, testing=20, tooling=11)
    result = find_neighbors(query, [far, same_repo, close, query_record], limit=10)
    assert [row["repository_name"] for row in result["neighbors"]] == ["org/close", "org/far"]
    assert result["neighbors"][0]["distance"] < result["neighbors"][1]["distance"]
    assert result["cohort"]["excluded"]["same_repository"] == 2
    assert "quality score" in result["distance_semantics"]["meaning"]


def test_scan_fingerprint_is_compatible_with_index_semantic_model():
    fingerprint = fingerprint_from_scan(_scan())
    assert fingerprint["measurement_model"] == MEASUREMENT_MODEL
    assert fingerprint["code_category_shares"]["core-product"] == 0.7
    assert fingerprint["relationship_count"] == 10


def test_select_query_record_prefers_newest_matching_record():
    old = _index_record("org/query", sha="1" * 40, scanned_at="2026-08-01T00:00:00Z")
    new = _index_record("org/query", sha="2" * 40, scanned_at="2026-08-10T00:00:00Z")
    assert select_query_record([new, old], "ORG/QUERY")["repository"]["sha"] == "2" * 40
    assert select_query_record([new, old], "org/query", sha="1" * 40)["repository"]["sha"] == "1" * 40


def test_report_is_self_contained_escaped_and_explains_distance():
    query = fingerprint_from_index_record(_index_record("org/<query>", sha="1" * 40))
    peer = _index_record("org/<peer>", sha="2" * 40)
    result = find_neighbors(query, [peer], limit=1)
    html = build_neighbors_report_html(result)
    assert "Structural Neighborhood" in html
    assert "Nearest means structurally similar, not better" in html
    assert "&lt;peer&gt;" in html
    assert "org/<peer>" not in html
    assert "Distance decomposition" in html
    assert "https://" not in html.lower()
    assert "<script src=" not in html.lower()


def test_neighbors_cli_reads_corpus_and_writes_json_and_report(tmp_path: Path):
    corpus = tmp_path / "corpus.jsonl"
    records = [
        _index_record("org/query", sha="1" * 40),
        _index_record("org/peer", sha="2" * 40, product=69, testing=20, tooling=11),
        _index_record("org/far", sha="3" * 40, product=20, testing=50, tooling=30, depth=4, index=50.0),
    ]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    assert len(load_corpus(corpus)) == 3
    output = tmp_path / "neighbors.json"
    report = tmp_path / "neighbors.html"
    assert neighbors_main([
        str(corpus), "--repo", "org/query", "--json", str(output), "--report", str(report), "--quiet"
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["neighbors"][0]["repository_name"] == "org/peer"
    assert report.exists()
    assert "Structural Neighborhood" in report.read_text(encoding="utf-8")
