from __future__ import annotations

import json
from pathlib import Path

from ouroboros.context import MEASUREMENT_MODEL, fingerprint_from_context_record, semantic_model_for_version, structural_context
from ouroboros.context_cli import main as context_main
from ouroboros.context_report import build_context_report_html


def _record(name: str, *, sha: str, product: float, machinery: float, depth: int, index: float, scanned_at: str, version: str = "0.9.0") -> dict:
    return {
        "schema": "ouroboros-index-record/v1",
        "status": "ok",
        "scanned_at": scanned_at,
        "repository": {"name": name, "sha": sha, "id": abs(hash(name)) % 100000},
        "analyzer": {"name": "Ouroboros", "version": version, "source_revision": "a" * 40, "canonical": True},
        "measurement": {
            "baseline": {"direct_product_share": product, "tooling_share": machinery, "scaffolding_ratio": machinery / product if product else None},
            "semantic": {"relationship_count": 10, "exact_resolution_rate": 0.8, "max_recursive_depth": depth, "semantic_ouroboros_index": index, "far_from_value_symbol_share": 0.2},
            "category_code_lines": {"core-product": int(product * 1000), "testing": int(machinery * 1000)},
            "category_symbol_counts": {"core-product": 10, "testing": 5},
        },
    }


def test_context_declares_current_measurement_generation_without_open_ending_future_versions():
    assert semantic_model_for_version("0.9.0") == MEASUREMENT_MODEL
    assert semantic_model_for_version("0.10.0") == MEASUREMENT_MODEL
    assert semantic_model_for_version("0.11.0") is None


def test_structural_context_dedupes_repositories_and_reports_neutral_percentiles():
    old = _record("org/a", sha="1" * 40, product=0.2, machinery=0.8, depth=4, index=60, scanned_at="2026-08-01T00:00:00Z")
    new = _record("org/a", sha="2" * 40, product=0.5, machinery=0.5, depth=2, index=30, scanned_at="2026-08-10T00:00:00Z")
    query_record = _record("org/query", sha="3" * 40, product=0.9, machinery=0.1, depth=0, index=5, scanned_at="2026-08-10T00:00:00Z")
    other = _record("org/b", sha="4" * 40, product=0.7, machinery=0.3, depth=1, index=15, scanned_at="2026-08-10T00:00:00Z", version="0.8.0")
    query = fingerprint_from_context_record(query_record)
    result = structural_context(query, [old, new, other, query_record])
    assert result["cohort"]["repositories"] == 3
    assert result["dimensions"]["product_share"]["band"] == "upper-tail"
    assert result["dimensions"]["machinery_share"]["band"] == "lower-tail"
    assert "not a quality rank" in result["semantics"]["percentile"]


def test_context_report_is_self_contained_and_nonjudgmental():
    query_record = _record("org/<query>", sha="1" * 40, product=0.6, machinery=0.4, depth=1, index=10, scanned_at="2026-08-10T00:00:00Z")
    peer = _record("org/peer", sha="2" * 40, product=0.4, machinery=0.6, depth=2, index=20, scanned_at="2026-08-10T00:00:00Z")
    result = structural_context(fingerprint_from_context_record(query_record), [query_record, peer])
    text = build_context_report_html(result)
    assert "Not a leaderboard" in text
    assert "https://" not in text.lower()
    assert "<script src=" not in text.lower()


def test_context_cli_reads_corpus_and_writes_json_and_report(tmp_path: Path):
    records = [
        _record("org/query", sha="1" * 40, product=0.8, machinery=0.2, depth=1, index=10, scanned_at="2026-08-10T00:00:00Z"),
        _record("org/peer", sha="2" * 40, product=0.4, machinery=0.6, depth=3, index=40, scanned_at="2026-08-10T00:00:00Z"),
    ]
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    output = tmp_path / "context.json"
    report = tmp_path / "context.html"
    assert context_main([str(corpus), "--repo", "org/query", "--json", str(output), "--report", str(report), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["cohort"]["repositories"] == 2
    assert payload["dimensions"]["product_share"]["available"] is True
    assert report.exists()
