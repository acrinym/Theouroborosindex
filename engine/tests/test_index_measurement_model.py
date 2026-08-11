from __future__ import annotations

from ouroboros.index_cli import _stamp_measurement_model
from ouroboros.neighbors import MEASUREMENT_MODEL, fingerprint_from_index_record


def _record() -> dict:
    return {
        "status": "ok",
        "repository": {"name": "org/repo", "sha": "1" * 40},
        "analyzer": {"version": "0.13.0", "canonical": True},
        "measurement": {
            "baseline": {
                "direct_product_share": 0.7,
                "tooling_share": 0.3,
                "scaffolding_ratio": 3 / 7,
            },
            "semantic": {
                "relationship_count": 10,
                "exact_resolution_rate": 0.8,
                "max_recursive_depth": 1,
                "semantic_ouroboros_index": 10.0,
                "far_from_value_symbol_share": 0.2,
            },
            "category_code_lines": {
                "core-product": 70,
                "testing": 20,
                "developer-tooling": 10,
            },
            "category_symbol_counts": {
                "core-product": 7,
                "testing": 2,
                "developer-tooling": 1,
            },
        },
    }


def test_current_index_record_stamps_measurement_model_explicitly():
    record = _stamp_measurement_model(_record())
    assert record["measurement"]["measurement_model"] == MEASUREMENT_MODEL
    assert fingerprint_from_index_record(record)["measurement_model"] == MEASUREMENT_MODEL


def test_non_success_record_is_not_rewritten():
    record = {"status": "failed", "reason": {"code": "example"}}
    assert _stamp_measurement_model(record) is record
    assert "measurement" not in record
