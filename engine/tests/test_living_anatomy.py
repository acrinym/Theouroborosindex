from __future__ import annotations

import json
from pathlib import Path

from ouroboros.anatomy import anatomy_fingerprint, spatial_layout
from ouroboros.compare_cli import main as compare_main
from ouroboros.comparison import compare_scans
from ouroboros.evolution_report import build_evolution_report_html
from ouroboros.identity import static_git_sha
from ouroboros.living_report import build_living_report_html
from ouroboros.model import Analysis, Category, Component, DirectoryProfile, Metrics
from ouroboros.semantic.model import SemanticGraph, SemanticMetrics


def _analysis(*, malicious: bool = False) -> Analysis:
    product_path = "src/<script>alert(1)</script>.py" if malicious else "src/app.py"
    components = [
        Component(product_path, "python", 80, 70, 1200, category=Category.CORE_PRODUCT, confidence=0.95, value_distance=0),
        Component("tests/test_app.py", "python", 50, 40, 850, category=Category.TESTING, confidence=0.93, value_distance=2),
    ]
    metrics = Metrics(
        direct_product_share=70 / 110,
        product_plus_essential_share=70 / 110,
        tooling_share=40 / 110,
        meta_machinery_share=0.0,
        assurance_ratio=40 / 110,
        audit_ratio=0.0,
        scaffolding_ratio=40 / 70,
        far_from_value_share=40 / 110,
        max_audit_depth=1,
        ouroboros_index=8.0,
        category_code_lines={Category.CORE_PRODUCT.value: 70, Category.TESTING.value: 40},
    )
    profiles = [
        DirectoryProfile("src", 70, 70, 0, 0, 0.0, 0.0),
        DirectoryProfile("tests", 40, 0, 0, 40, 1.0, None),
    ]
    return Analysis(".", components, metrics, [], profiles, [])


def _semantic() -> SemanticGraph:
    metrics = SemanticMetrics(
        symbol_count=2,
        relationship_count=0,
        resolved_relationships=0,
        probable_relationships=0,
        unresolved_relationships=0,
        product_symbols=1,
        machinery_symbols=1,
        audit_symbols=0,
        meta_symbols=0,
        product_reachable_symbols=1,
        far_from_value_symbols=1,
        max_value_distance=2,
        max_recursive_depth=1,
        direct_product_symbol_share=0.5,
        machinery_symbol_share=0.5,
        audit_symbol_share=0.0,
        meta_symbol_share=0.0,
        scaffolding_symbol_ratio=1.0,
        far_from_value_symbol_share=0.5,
        resolution_rate=0.0,
        exact_resolution_rate=0.0,
        semantic_ouroboros_index=12.0,
    )
    return SemanticGraph(metrics=metrics)


def _payload(*, version="0.6.0", sha="a" * 40, process=0, depth=1, index=10.0, product=70, testing=40, exact=0.8, relationships=10, source="1" * 40, inversion=False, chain=None):
    machinery = testing + process
    total = product + machinery
    profile = {
        "path": "src",
        "code_lines": total,
        "product_lines": product,
        "essential_lines": 0,
        "machinery_lines": machinery,
        "tooling_share": machinery / total if total else 0,
        "scaffolding_ratio": machinery / product if product else None,
        "is_inversion": inversion,
    }
    chains = []
    if chain:
        chains = [{"symbol_ids": chain, "categories": ["core-product"] + ["testing"] * (len(chain) - 1), "relationships": ["calls"] * (len(chain) - 1), "depth": len(chain) - 1}]
    return {
        "schema": {"name": "ouroboros-scan", "version": 2},
        "analyzer": {"name": "Ouroboros", "version": version, "source_sha": source},
        "repository": "/repo",
        "repository_identity": {"git_sha": sha},
        "scan": {"canonical": True, "target_execution": False, "relationship_topology": "exact-only"},
        "baseline": {
            "metrics": {
                "direct_product_share": product / total if total else 0,
                "tooling_share": machinery / total if total else 0,
                "scaffolding_ratio": machinery / product if product else None,
                "category_code_lines": {"core-product": product, "testing": testing, "process-machinery": process},
            },
            "directory_profiles": [profile],
        },
        "semantic": {
            "metrics": {
                "relationship_count": relationships,
                "exact_resolution_rate": exact,
                "max_recursive_depth": depth,
                "semantic_ouroboros_index": index,
                "far_from_value_symbol_share": 0.2,
            },
            "chains": chains,
        },
    }


def test_spatial_layout_is_deterministic_and_mass_preserving():
    baseline = _analysis()
    first = [rect.to_dict() for rect in spatial_layout(baseline)]
    second = [rect.to_dict() for rect in spatial_layout(baseline)]
    assert first == second
    assert sum(rect["weight"] for rect in first if rect["kind"] == "file") == 110


def test_fingerprint_is_stable_and_multidimensional():
    baseline = _analysis()
    semantic = _semantic()
    assert anatomy_fingerprint(baseline, semantic) == anatomy_fingerprint(baseline, semantic)
    fingerprint = anatomy_fingerprint(baseline, semantic)
    assert fingerprint["category_shares"]["core-product"] == 70 / 110
    assert fingerprint["category_shares"]["testing"] == 40 / 110
    assert fingerprint["recursive_depth"] == 1
    assert "semantic_index" in fingerprint


def test_living_report_is_self_contained_and_escapes_repository_strings():
    html = build_living_report_html("repo<script>x</script>", _analysis(malicious=True), _semantic())
    assert "Living repository map" in html
    assert "Anatomy fingerprint" in html
    assert ".repo-map .cat-core-product > rect { fill:#2f8f72; }" in html
    assert ".repo-map .cat-testing > rect { fill:#a987db; }" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script src=" not in html.lower()
    assert "<link rel=" not in html.lower()
    assert "@import" not in html.lower()
    assert "https://" not in html.lower()


def test_compare_scans_reports_deltas_crossovers_and_chain_change():
    before = _payload(product=100, testing=20, process=0, depth=1, index=4.0, sha="a" * 40, chain=["product", "test"])
    after = _payload(product=80, testing=60, process=40, depth=3, index=18.0, sha="b" * 40, inversion=True, chain=["product", "tool", "verify", "meta"])
    comparison = compare_scans(before, after)
    assert comparison["category_deltas"]["process-machinery"]["delta"] == 40
    assert comparison["measurement"]["target_sha_changed"] is True
    assert comparison["measurement"]["like_for_like_analyzer"] is True
    assert comparison["metrics"]["recursive_depth"]["delta"] == 2
    assert comparison["inversion_hotspots"]["added"] == ["src"]
    assert comparison["crossovers"][0]["path"] == "src"
    assert comparison["deepest_exact_chains"]["added"]


def test_analyzer_mismatch_is_disclosed_and_empty_coverage_is_na():
    before = _payload(version="0.5.0", relationships=0, exact=1.0)
    after = _payload(version="0.6.0", relationships=0, exact=1.0)
    comparison = compare_scans(before, after)
    assert comparison["measurement"]["analyzer_version_changed"] is True
    assert comparison["measurement"]["like_for_like_analyzer"] is False
    assert comparison["metrics"]["exact_coverage"]["before"] is None
    assert comparison["metrics"]["exact_coverage"]["after"] is None
    html = build_evolution_report_html(comparison)
    assert "not perfectly like-for-like" in html
    assert "n/a" in html
    assert "https://" not in html.lower()


def test_compare_cli_writes_json_and_self_contained_report(tmp_path: Path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    output = tmp_path / "comparison.json"
    report = tmp_path / "evolution.html"
    before.write_text(json.dumps(_payload()), encoding="utf-8")
    after.write_text(json.dumps(_payload(product=60, testing=50, process=20, sha="b" * 40)), encoding="utf-8")
    assert compare_main([str(before), str(after), "--json", str(output), "--report", str(report), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == {"name": "ouroboros-comparison", "version": 1}
    html = report.read_text(encoding="utf-8")
    assert "Software Evolution" in html
    assert "<script src=" not in html.lower()
    assert "https://" not in html.lower()


def test_static_git_sha_reads_loose_ref_without_executing_git(tmp_path: Path):
    git_dir = tmp_path / ".git"
    refs = git_dir / "refs" / "heads"
    refs.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (refs / "main").write_text("a" * 40 + "\n", encoding="utf-8")
    assert static_git_sha(tmp_path) == "a" * 40
