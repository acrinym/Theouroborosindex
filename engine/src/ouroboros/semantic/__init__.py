"""Semantic source graph for Ouroboros 0.2.

The semantic layer parses source without executing target repository code and emits a
language-neutral symbol/relationship graph used for reachability and Distance From Value.
"""

from .adapters import AdapterRegistry, PythonAstAdapter, TreeSitterAdapter
from .api import SemanticBuildOptions, build_semantic_graph
from .model import EdgeKind, Resolution, SemanticGraph, SemanticMetrics, Symbol, SymbolKind

__all__ = [
    "AdapterRegistry",
    "EdgeKind",
    "PythonAstAdapter",
    "Resolution",
    "SemanticBuildOptions",
    "SemanticGraph",
    "SemanticMetrics",
    "Symbol",
    "SymbolKind",
    "TreeSitterAdapter",
    "build_semantic_graph",
]
