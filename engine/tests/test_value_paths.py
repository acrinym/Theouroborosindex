from __future__ import annotations

import json
from pathlib import Path

import pytest

from ouroboros.capabilities import Capability, CapabilityAtlas, CapabilityEvidence
from ouroboros.model import Category
from ouroboros.semantic.model import EdgeKind, Resolution, SemanticEdge, SemanticGraph, Symbol, SymbolKind
from ouroboros.value_paths import ValuePathError, select_capability, trace_value_path
from ouroboros.value_paths_cli import main as paths_main


def symbol(symbol_id: str, name: str, path: str, category: Category) -> Symbol:
    return Symbol(
        id=symbol_id,
        path=path,
        language="python",
        kind=SymbolKind.FUNCTION,
        name=name,
        qualified_name=name,
        start_line=1,
        end_line=2,
        category=category,
        role_confidence=1.0,
        role_source="test",
    )


def capability(anchor: str, name: str = "import-project") -> Capability:
    return Capability(
        id=f"cli:pyproject.toml:2:{name}",
        kind="cli",
        name=name,
        path="pyproject.toml",
        line=2,
        symbol_id=anchor,
        evidence=[CapabilityEvidence("packaging-entrypoint", "pyproject.toml", 2, "test")],
    )


def edge(source: str, target: str, resolution: Resolution = Resolution.EXACT) -> SemanticEdge:
    return SemanticEdge(
        source_id=source,
        kind=EdgeKind.CALLS,
        target_name=target,
        target_id=target if resolution != Resolution.UNRESOLVED else None,
        resolution=resolution,
        evidence=f"{source} calls {target}",
    )


def test_strongest_value_path_prefers_longest_exact_call_journey_then_exposes_alternative():
    symbols = {
        "main": symbol("main", "main", "cli.py", Category.USER_SURFACE),
        "importer": symbol("importer", "import_project", "importer.py", Category.CORE_PRODUCT),
        "parse": symbol("parse", "parse", "parser.py", Category.ESSENTIAL_SUPPORT),
        "store": symbol("store", "store", "store.py", Category.CORE_PRODUCT),
        "help": symbol("help", "help", "cli.py", Category.USER_SURFACE),
    }
    graph = SemanticGraph(
        symbols=symbols,
        edges=[
            edge("main", "importer"),
            edge("importer", "parse"),
            edge("parse", "store"),
            edge("main", "help"),
        ],
    )
    analysis = trace_value_path(capability("main"), graph)

    assert [step.symbol_id for step in analysis.strongest.steps] == ["main", "importer", "parse", "store"]
    assert analysis.strongest.depth == 3
    assert analysis.strongest.distinct_files == 4
    assert [step.symbol_id for step in analysis.alternatives[0].steps] == ["main", "help"]
    assert analysis.to_dict()["selection"]["quality_judgment"] is False


def test_probable_and_unresolved_calls_are_boundaries_not_canonical_steps():
    symbols = {
        "main": symbol("main", "main", "cli.py", Category.USER_SURFACE),
        "exact": symbol("exact", "exact_work", "service.py", Category.CORE_PRODUCT),
        "guess": symbol("guess", "maybe_work", "guess.py", Category.CORE_PRODUCT),
    }
    probable = edge("exact", "guess", Resolution.PROBABLE)
    unresolved = edge("exact", "external_missing", Resolution.UNRESOLVED)
    graph = SemanticGraph(symbols=symbols, edges=[edge("main", "exact"), probable, unresolved])

    analysis = trace_value_path(capability("main"), graph)
    assert [step.symbol_id for step in analysis.strongest.steps] == ["main", "exact"]
    assert analysis.strongest.probable_call_boundaries == 1
    assert analysis.strongest.unresolved_call_boundaries == 1
    assert "guess" not in {step.symbol_id for step in analysis.strongest.steps}
    assert any("not traversed" in warning for warning in analysis.warnings)


def test_cycles_do_not_repeat_symbols_and_depth_bound_is_explicit():
    symbols = {
        "a": symbol("a", "a", "a.py", Category.USER_SURFACE),
        "b": symbol("b", "b", "b.py", Category.CORE_PRODUCT),
        "c": symbol("c", "c", "c.py", Category.CORE_PRODUCT),
        "d": symbol("d", "d", "d.py", Category.CORE_PRODUCT),
    }
    graph = SemanticGraph(symbols=symbols, edges=[edge("a", "b"), edge("b", "a"), edge("b", "c"), edge("c", "d")])
    normal = trace_value_path(capability("a"), graph)
    assert [step.symbol_id for step in normal.strongest.steps] == ["a", "b", "c", "d"]
    assert len({step.symbol_id for step in normal.strongest.steps}) == len(normal.strongest.steps)

    bounded = trace_value_path(capability("a"), graph, max_depth=2)
    assert [step.symbol_id for step in bounded.strongest.steps] == ["a", "b", "c"]
    assert bounded.truncated is True


def test_capability_selector_requires_unique_anchored_match():
    atlas = CapabilityAtlas(capabilities=[capability("a", "import"), capability("b", "import-all")])
    with pytest.raises(ValuePathError, match="Multiple anchored"):
        select_capability(atlas, None)
    with pytest.raises(ValuePathError, match="matches multiple"):
        select_capability(atlas, "impor")
    assert select_capability(atlas, "import-all").symbol_id == "b"


def test_value_paths_cli_lists_and_traces_packaged_entrypoint(tmp_path: Path, capsys):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.0.1"\n[project.scripts]\ndemo = "app:main"\n',
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "def main():\n    return work()\n\ndef work():\n    return finish()\n\ndef finish():\n    return 1\n",
        encoding="utf-8",
    )

    assert paths_main([str(tmp_path), "--list"]) == 0
    listing = capsys.readouterr().out
    assert "demo" in listing
    assert "cli" in listing

    output = tmp_path / "value-path.json"
    report = tmp_path / "value-path.html"
    assert paths_main([
        str(tmp_path), "--capability", "demo", "--json", str(output), "--report", str(report), "--quiet"
    ]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    strongest = payload["value_path"]["strongest"]
    assert [step["name"] for step in strongest["steps"]] == ["main", "work", "finish"]
    assert strongest["depth"] == 2
    assert payload["scan"]["canonical_relationships"] == "EXACT CALLS only"
    assert report.exists()
    assert "Strongest exact call path" in report.read_text(encoding="utf-8")


def test_value_paths_rejects_depth_above_safe_recursive_bound():
    graph = SemanticGraph(symbols={}, edges=[])
    with pytest.raises(ValuePathError, match="max_depth cannot exceed 200"):
        trace_value_path(capability("missing"), graph, max_depth=201)


def test_value_paths_cli_rejects_list_with_quiet(tmp_path: Path):
    with pytest.raises(SystemExit) as exc:
        paths_main([str(tmp_path), "--list", "--quiet"])
    assert exc.value.code == 2
