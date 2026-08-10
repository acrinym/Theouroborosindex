from __future__ import annotations

from pathlib import Path

from ouroboros.cli import build_parser
from ouroboros.model import Analysis, Category, Component, DirectoryProfile, Metrics, Signal
from ouroboros.report import build_report_html, write_report
from ouroboros.semantic.model import EdgeKind, Resolution, SemanticChain, SemanticEdge, SemanticGraph, SemanticMetrics, Symbol, SymbolKind


def _fixture():
    baseline = Analysis(
        root="/tmp/demo",
        components=[
            Component(path="src/app.py", language="python", lines=10, code_lines=8, bytes=80, category=Category.CORE_PRODUCT, confidence=0.9, signals=[Signal(Category.CORE_PRODUCT, 3.0, "src product path")], value_distance=0),
            Component(path="tools/audit.py", language="python", lines=14, code_lines=12, bytes=120, category=Category.AUDIT_PROVENANCE, confidence=0.8, signals=[Signal(Category.AUDIT_PROVENANCE, 4.0, "checks receipt evidence")], value_distance=3),
        ],
        metrics=Metrics(
            direct_product_share=0.4, product_plus_essential_share=0.4, tooling_share=0.6,
            meta_machinery_share=0.0, assurance_ratio=0.6, audit_ratio=0.6,
            scaffolding_ratio=1.5, far_from_value_share=0.0, max_audit_depth=1,
            ouroboros_index=9.0,
            category_code_lines={Category.CORE_PRODUCT.value: 8, Category.AUDIT_PROVENANCE.value: 12},
        ),
        audit_chains=[],
        directory_profiles=[DirectoryProfile(path="src", code_lines=20, product_lines=8, essential_lines=0, machinery_lines=12, tooling_share=0.6, scaffolding_ratio=1.5)],
        warnings=["sample warning"],
    )
    product = Symbol(id="src/app.py::run@1", path="src/app.py", language="python", kind=SymbolKind.FUNCTION, name="run", qualified_name="run", start_line=1, end_line=2, category=Category.CORE_PRODUCT, value_distance=0, role_confidence=0.95, role_source="file-seed")
    audit = Symbol(id="tools/audit.py::verify@1", path="tools/audit.py", language="python", kind=SymbolKind.FUNCTION, name="verify", qualified_name="verify", start_line=1, end_line=4, category=Category.AUDIT_PROVENANCE, value_distance=3, role_confidence=0.88, role_source="symbol-evidence")
    edge = SemanticEdge(source_id=audit.id, kind=EdgeKind.CALLS, target_name="run", target_id=product.id, resolution=Resolution.EXACT, evidence="qualified call")
    semantic = SemanticGraph(
        symbols={product.id: product, audit.id: audit},
        edges=[edge],
        chains=[SemanticChain(symbol_ids=[product.id, audit.id], categories=[Category.CORE_PRODUCT, Category.AUDIT_PROVENANCE], relationships=[EdgeKind.CALLS])],
        metrics=SemanticMetrics(
            symbol_count=2, relationship_count=1, resolved_relationships=1, probable_relationships=0,
            unresolved_relationships=0, product_symbols=1, machinery_symbols=1, audit_symbols=1,
            meta_symbols=0, product_reachable_symbols=2, far_from_value_symbols=0,
            max_value_distance=3, max_recursive_depth=1, direct_product_symbol_share=0.5,
            machinery_symbol_share=0.5, audit_symbol_share=0.5, meta_symbol_share=0.0,
            scaffolding_symbol_ratio=1.0, far_from_value_symbol_share=0.0, resolution_rate=1.0,
            exact_resolution_rate=1.0, semantic_ouroboros_index=10.0,
        ),
    )
    return baseline, semantic


def test_report_is_self_contained_and_explains_evidence():
    baseline, semantic = _fixture()
    html = build_report_html("/tmp/demo", baseline, semantic)
    assert "Repository Anatomy" in html
    assert "What Ouroboros found" in html
    assert "Scaffolding inversion hotspots" in html
    assert "Deepest exact chains" in html
    assert "File evidence explorer" in html
    assert "Symbol role explorer" in html
    assert "qualified call" in html
    assert "checks receipt evidence" in html
    assert "https://" not in html
    assert "http://" not in html


def test_write_report_creates_parent_directories(tmp_path: Path):
    baseline, semantic = _fixture()
    target = tmp_path / "nested" / "report.html"
    result = write_report("/tmp/demo", baseline, semantic, target)
    assert result == target.resolve()
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_report_flag_has_friendly_default_filename():
    args = build_parser().parse_args([".", "--report"])
    assert args.report_path == "ouroboros-report.html"
    args = build_parser().parse_args([".", "--report", "my-report.html"])
    assert args.report_path == "my-report.html"
