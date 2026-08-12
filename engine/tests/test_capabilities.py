from __future__ import annotations

from ouroboros.analyze import analyze_repository
from ouroboros.capabilities import build_capability_atlas
from ouroboros.cli import main as ouroboros_main
from ouroboros.model import Category, Component
from ouroboros.scanner import ScannedFile
from ouroboros.semantic import EdgeKind, Resolution, SymbolKind, build_semantic_graph
from ouroboros.semantic.graph import finalize_graph
from ouroboros.semantic.model import SemanticEdge, SemanticGraph, Symbol


def scanned(path: str, text: str, category: Category, language: str = "python") -> ScannedFile:
    return ScannedFile(
        Component(
            path=path,
            language=language,
            lines=len(text.splitlines()),
            code_lines=len(text.splitlines()),
            bytes=len(text.encode()),
            category=category,
        ),
        text,
    )


def test_rating_only_returns_original_file_level_index_without_semantic_scan(tmp_path, monkeypatch, capsys):
    (tmp_path / "game.py").write_text("def play():\n    return 1\n", encoding="utf-8")
    expected = analyze_repository(tmp_path).metrics.ouroboros_index

    def forbidden_scan(*args, **kwargs):
        raise AssertionError("semantic scan should not run in --rating-only mode")

    monkeypatch.setattr("ouroboros.cli.scan", forbidden_scan)
    assert ouroboros_main([str(tmp_path), "--rating-only"]) == 0
    output = capsys.readouterr().out.strip()
    assert output == f"{expected:.6f}".rstrip("0").rstrip(".")
    assert output.replace(".", "", 1).isdigit()


def test_pyproject_cli_entrypoint_maps_to_exact_implementation_neighborhood():
    files = [
        scanned(
            "pyproject.toml",
            '[project.scripts]\ndemo = "app:main"\n',
            Category.ESSENTIAL_SUPPORT,
            "toml",
        ),
        scanned(
            "app.py",
            "def main():\n    return work()\n\ndef work():\n    return 1\n",
            Category.USER_SURFACE,
        ),
    ]
    graph = build_semantic_graph(files)
    atlas = build_capability_atlas(files, graph)
    capability = next(item for item in atlas.capabilities if item.kind == "cli" and item.name == "demo")

    assert capability.symbol_id is not None
    names = {item["name"] for item in capability.implementation_symbols}
    assert {"main", "work"} <= names
    assert capability.exact_relationships
    assert capability.unresolved_relationships >= 0


def test_python_route_is_discovered_and_anchored_to_handler():
    files = [
        scanned(
            "api.py",
            '@app.get("/items")\ndef items():\n    return load_items()\n\ndef load_items():\n    return []\n',
            Category.USER_SURFACE,
        )
    ]
    graph = build_semantic_graph(files)
    atlas = build_capability_atlas(files, graph)
    route = next(item for item in atlas.capabilities if item.kind == "http-route")

    assert route.name == "GET /items"
    assert route.symbol_id is not None
    handler = graph.symbols[route.symbol_id]
    assert handler.name == "items"
    assert "load_items" in {item["name"] for item in route.implementation_symbols}


def test_probable_relationship_never_enters_capability_implementation_neighborhood():
    root = Symbol(
        id="api.py::run@1",
        path="api.py",
        language="python",
        kind=SymbolKind.FUNCTION,
        name="run",
        qualified_name="run",
        start_line=1,
        end_line=1,
        category=Category.USER_SURFACE,
        role_confidence=1.0,
        role_source="test",
    )
    target = Symbol(
        id="service.py::work@1",
        path="service.py",
        language="python",
        kind=SymbolKind.FUNCTION,
        name="work",
        qualified_name="work",
        start_line=1,
        end_line=1,
        category=Category.CORE_PRODUCT,
    )
    graph = finalize_graph(SemanticGraph(
        symbols={root.id: root, target.id: target},
        edges=[SemanticEdge(
            source_id=root.id,
            kind=EdgeKind.CALLS,
            target_name="work",
            target_id=target.id,
            resolution=Resolution.PROBABLE,
            evidence="ambiguous candidate",
        )],
    ))
    files = [scanned("api.py", "def run():\n    pass\n", Category.USER_SURFACE)]
    atlas = build_capability_atlas(files, graph)
    capability = next(item for item in atlas.capabilities if item.symbol_id == root.id)

    assert {item["id"] for item in capability.implementation_symbols} == {root.id}
    assert capability.exact_relationships == []
    assert capability.probable_relationships == 1


def test_package_bin_preserves_hidden_directory_in_target_path():
    root = Symbol(
        id=".bin/cli.js::main@1",
        path=".bin/cli.js",
        language="javascript",
        kind=SymbolKind.FUNCTION,
        name="main",
        qualified_name="main",
        start_line=1,
        end_line=2,
        category=Category.USER_SURFACE,
        role_confidence=1.0,
        role_source="test",
    )
    graph = finalize_graph(SemanticGraph(symbols={root.id: root}, edges=[]))
    files = [scanned(
        "package.json",
        '{"name":"demo","bin":"./.bin/cli.js"}',
        Category.ESSENTIAL_SUPPORT,
        "json",
    )]

    atlas = build_capability_atlas(files, graph)
    capability = next(item for item in atlas.capabilities if item.kind == "cli" and item.name == "demo")

    assert capability.symbol_id == root.id
