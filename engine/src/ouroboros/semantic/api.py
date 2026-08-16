from __future__ import annotations

from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from ouroboros.scanner import ScannedFile

from .adapters import AdapterRegistry
from .graph import DEFAULT_CHAIN_EXPANSION_BUDGET, finalize_graph
from .model import ParseDiagnostic, SemanticGraph
from .roles import refine_symbol_categories


@dataclass(slots=True)
class SemanticBuildOptions:
    fail_on_missing_adapter: bool = False
    max_chain_expansions: int = DEFAULT_CHAIN_EXPANSION_BUDGET


def _checkpoint(
    telemetry: MutableMapping[str, Any] | None,
    checkpoint: Callable[[], None] | None,
) -> None:
    if telemetry is not None and checkpoint is not None:
        checkpoint()


def build_semantic_graph(
    scanned_files: list[ScannedFile],
    *,
    file_dependencies: dict[str, set[str]] | None = None,
    registry: AdapterRegistry | None = None,
    options: SemanticBuildOptions | None = None,
    telemetry: MutableMapping[str, Any] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> SemanticGraph:
    registry = registry or AdapterRegistry()
    options = options or SemanticBuildOptions()
    graph = SemanticGraph()

    parse_started = perf_counter()
    if telemetry is not None:
        telemetry.update({
            "semantic_stage": "parse",
            "semantic_files_total": len(scanned_files),
            "semantic_files_parsed": 0,
            "semantic_parse_seconds": 0.0,
        })
        _checkpoint(telemetry, checkpoint)

    for index, item in enumerate(scanned_files, 1):
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
        else:
            try:
                unit = adapter.parse(item)
            except Exception as exc:
                graph.diagnostics.append(ParseDiagnostic(
                    path=item.component.path,
                    language=item.component.language,
                    message=f"Semantic adapter failed: {type(exc).__name__}: {exc}",
                    severity="error",
                ))
            else:
                graph.add_symbols(unit.symbols)
                graph.edges.extend(unit.edges)
                graph.diagnostics.extend(unit.diagnostics)

        if telemetry is not None and (index % 500 == 0 or index == len(scanned_files)):
            telemetry["semantic_files_parsed"] = index
            telemetry["semantic_parse_seconds"] = perf_counter() - parse_started
            telemetry["semantic_symbols_so_far"] = len(graph.symbols)
            telemetry["semantic_edges_so_far"] = len(graph.edges)
            _checkpoint(telemetry, checkpoint)

    role_started = perf_counter()
    if telemetry is not None:
        telemetry["semantic_stage"] = "role-refinement"
        telemetry["semantic_parse_seconds"] = role_started - parse_started
        _checkpoint(telemetry, checkpoint)
    refine_symbol_categories(graph, scanned_files)
    if telemetry is not None:
        telemetry["semantic_role_refinement_seconds"] = perf_counter() - role_started
        _checkpoint(telemetry, checkpoint)

    finalize_started = perf_counter()
    if telemetry is not None:
        telemetry["semantic_stage"] = "graph-finalization"
        _checkpoint(telemetry, checkpoint)
    result = finalize_graph(
        graph,
        file_dependencies=file_dependencies,
        max_chain_expansions=options.max_chain_expansions,
    )
    finished = perf_counter()
    if telemetry is not None:
        telemetry.update({
            "semantic_stage": "complete",
            "semantic_finalize_seconds": finished - finalize_started,
            "semantic_total_seconds": finished - parse_started,
            "semantic_symbols": len(graph.symbols),
            "semantic_edges": len(graph.edges),
        })
        _checkpoint(telemetry, checkpoint)
    return result
