from __future__ import annotations

from dataclasses import dataclass

from ouroboros.scanner import ScannedFile

from .adapters import AdapterRegistry
from .graph import DEFAULT_CHAIN_EXPANSION_BUDGET, finalize_graph
from .model import ParseDiagnostic, SemanticGraph
from .roles import refine_symbol_categories


@dataclass(slots=True)
class SemanticBuildOptions:
    fail_on_missing_adapter: bool = False
    max_chain_expansions: int = DEFAULT_CHAIN_EXPANSION_BUDGET


def build_semantic_graph(
    scanned_files: list[ScannedFile],
    *,
    file_dependencies: dict[str, set[str]] | None = None,
    registry: AdapterRegistry | None = None,
    options: SemanticBuildOptions | None = None,
) -> SemanticGraph:
    registry = registry or AdapterRegistry()
    options = options or SemanticBuildOptions()
    graph = SemanticGraph()

    for item in scanned_files:
        adapter = registry.adapter_for(item.component.language)
        if adapter is None:
            if options.fail_on_missing_adapter:
                raise ValueError(f"No semantic adapter for language: {item.component.language}")
            graph.diagnostics.append(ParseDiagnostic(
                path=item.component.path,
                language=item.component.language,
                message="No semantic adapter; file remains represented by the baseline repository scan only",
                severity="info",
            ))
            continue
        try:
            unit = adapter.parse(item)
        except Exception as exc:
            graph.diagnostics.append(ParseDiagnostic(
                path=item.component.path,
                language=item.component.language,
                message=f"Semantic adapter failed: {type(exc).__name__}: {exc}",
                severity="error",
            ))
            continue
        graph.add_symbols(unit.symbols)
        graph.edges.extend(unit.edges)
        graph.diagnostics.extend(unit.diagnostics)

    refine_symbol_categories(graph, scanned_files)
    return finalize_graph(
        graph,
        file_dependencies=file_dependencies,
        max_chain_expansions=options.max_chain_expansions,
    )
