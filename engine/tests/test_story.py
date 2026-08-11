from __future__ import annotations

import json
from pathlib import Path

from ouroboros.story import compose_story
from ouroboros.story_cli import main as story_main
from ouroboros.story_report import build_story_report_html


def _scan(sha: str = "1" * 40) -> dict:
    return {
        "repository": "/repo/<name>",
        "repository_identity": {"git_sha": sha},
        "fingerprint": {"kind": "test"},
        "baseline": {"metrics": {"direct_product_share": 0.6, "tooling_share": 0.4, "scaffolding_ratio": 2 / 3}},
        "semantic": {"metrics": {"relationship_count": 10, "exact_resolution_rate": 0.8, "max_recursive_depth": 2, "semantic_ouroboros_index": 25.0}},
    }


def _history(sha: str = "1" * 40) -> dict:
    return {
        "range": {"to_sha": sha},
        "events": [{"type": "recursive-depth-change", "commit": sha, "before": 1, "after": 2, "subject": "depth <change>"}],
    }


def _drivers(sha: str = "1" * 40) -> dict:
    return {
        "after": {"sha": sha},
        "drivers": {"files": [{"path": "src/<driver>.py", "status": "changed", "before_category": "core-product", "after_category": "core-product", "delta_code_lines": 12}]},
    }


def _context(sha: str = "1" * 40) -> dict:
    return {
        "query": {"repository_sha": sha},
        "dimensions": {"product_share": {"label": "Direct product share", "available": True, "percentile": 75.0, "band": "middle-range", "cohort_size": 20}},
    }


def test_story_composes_existing_evidence_without_new_judgment():
    story = compose_story(_scan(), history=_history(), drivers=_drivers(), context=_context())
    assert story["current"]["recursive_depth"] == 2
    assert story["sources"] == {"current_scan": True, "bounded_history": True, "change_drivers": True, "structural_context": True}
    assert story["driver_relation"] == "current-commit"
    assert story["coherence"]["warnings"] == []
    assert "adds no new score" in story["semantics"]


def test_story_surfaces_artifact_commit_mismatches_instead_of_hiding_them():
    story = compose_story(_scan("1" * 40), history=_history("2" * 40), context=_context("3" * 40))
    assert len(story["coherence"]["warnings"]) == 2
    assert story["coherence"]["current_history_match"] is False
    assert story["coherence"]["current_context_match"] is False


def test_story_report_is_self_contained_and_escapes_artifact_text():
    story = compose_story(_scan(), history=_history(), drivers=_drivers(), context=_context())
    text = build_story_report_html(story)
    assert "Anatomy Story" in text
    assert "&lt;driver&gt;.py" in text
    assert "src/<driver>.py" not in text
    assert "https://" not in text.lower()
    assert "<script src=" not in text.lower()


def test_story_cli_writes_composed_json_and_report(tmp_path: Path):
    scan = tmp_path / "scan.json"
    history = tmp_path / "history.json"
    drivers = tmp_path / "drivers.json"
    context = tmp_path / "context.json"
    for path, value in ((scan, _scan()), (history, _history()), (drivers, _drivers()), (context, _context())):
        path.write_text(json.dumps(value), encoding="utf-8")
    output = tmp_path / "story.json"
    report = tmp_path / "story.html"
    assert story_main([str(scan), "--history", str(history), "--drivers", str(drivers), "--context", str(context), "--json", str(output), "--report", str(report), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["sources"]["structural_context"] is True
    assert report.exists()
