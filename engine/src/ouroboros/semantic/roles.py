from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePosixPath

from ouroboros.model import MACHINERY_CATEGORIES, PRODUCT_CATEGORIES, Category
from ouroboros.scanner import ScannedFile

from .model import SemanticGraph, Symbol, SymbolKind


# These are intentionally conservative. A product can legitimately have runtime
# concepts named "build", "pipeline", "receipt", "metrics", "verify", or
# "bootstrap". Those words alone must not turn business logic into repository
# machinery. Local machinery evidence is used mainly to split mixed-purpose files
# that the file classifier already identified as machinery.
ROLE_WORDS: dict[Category, set[str]] = {
    Category.META_MACHINERY: {"metaaudit", "auditofaudit", "auditquality", "reportvalidator"},
    Category.AUDIT_PROVENANCE: {"audit", "auditor", "provenance", "reconcile", "reconciliation", "traceability", "lineage"},
    Category.VERIFICATION: {"verify", "verified", "verification", "validate", "validation", "validator", "integrity", "checksum", "sha256", "invariant", "consistency"},
    Category.OBSERVABILITY: {"telemetry", "trace", "tracing", "logging", "logger", "monitor", "monitoring", "diagnostic", "diagnostics", "opentelemetry"},
    Category.PROCESS_MACHINERY: {"workflow", "deploy", "deployment", "packaging", "release"},
    Category.DEVELOPER_TOOLING: {"probe", "benchmark", "bench", "scaffold", "generator", "codemod", "migration", "bootstrap"},
    Category.USER_SURFACE: {"gui", "view", "screen", "dialog", "window", "controller", "route", "endpoint", "cli", "command", "menu", "frontend"},
    Category.ESSENTIAL_SUPPORT: {"config", "configuration", "storage", "store", "history", "cache", "serializer", "serialization", "parser", "loader", "filesystem", "transport", "protocol", "adapter", "catalog", "archive"},
}

_PATH_STRONG_WORDS = {
    Category.TESTING: {"test", "tests", "spec", "specs", "fixtures"},
    Category.AUDIT_PROVENANCE: {"audit", "audits", "provenance"},
    Category.META_MACHINERY: {"metaaudit"},
    Category.OBSERVABILITY: {"telemetry", "observability", "monitoring", "logging", "logger"},
    Category.VERIFICATION: {"verification", "validators", "validation"},
    Category.PROCESS_MACHINERY: {"workflow", "workflows", "ci", "cd", "deployment"},
    Category.DEVELOPER_TOOLING: {"scripts", "tools", "benchmarks", "probes"},
    Category.USER_SURFACE: {"gui", "views", "screens", "controllers", "routes", "frontend"},
}

_PRODUCT_PARENT_WORDS = {
    "src", "source", "sources", "app", "apps", "service", "services",
    "protocol", "protocols", "feature", "features", "domain", "core", "sync",
}


def _tokens(value: str) -> set[str]:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    parts = re.findall(r"[a-z0-9]+", value.lower().replace("_", " ").replace("-", " "))
    tokens = set(parts)
    tokens.update("".join(parts[index:index + 2]) for index in range(len(parts) - 1))
    tokens.update("".join(parts[index:index + 3]) for index in range(len(parts) - 2))
    return tokens


def _path_role(path: str) -> Category | None:
    tokens = _tokens(path)
    for category, words in _PATH_STRONG_WORDS.items():
        if tokens & words:
            return category
    return None


def _product_context(path: str) -> bool:
    parent = PurePosixPath(path).parent.as_posix()
    return bool(_tokens(parent) & _PRODUCT_PARENT_WORDS)


def _score_local(symbol: Symbol, snippet: str) -> dict[Category, float]:
    scores: dict[Category, float] = defaultdict(float)
    name_tokens = _tokens(symbol.name) | _tokens(symbol.qualified_name)
    snippet_tokens = _tokens(snippet[:4000])
    for category, words in ROLE_WORDS.items():
        name_hits = name_tokens & words
        body_hits = snippet_tokens & words
        if name_hits:
            scores[category] += 5.0 + min(2.0, 0.5 * (len(name_hits) - 1))
            if category == Category.META_MACHINERY:
                scores[category] += 1.0
        if body_hits:
            scores[category] += min(2.0, 0.35 * len(body_hits))
    return scores


def _best_local(scores: dict[Category, float]) -> tuple[Category, float, float] | None:
    if not scores:
        return None
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_category, best = ordered[0]
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    return best_category, best, second


def refine_symbol_categories(graph: SemanticGraph, scanned_files: list[ScannedFile]) -> None:
    """Refine mixed-purpose files without letting domain vocabulary hijack architecture.

    Rules are deliberately asymmetric:

    * dedicated path roles (tests, audit folders, telemetry folders, workflows, tools)
      are authoritative;
    * a symbol in a product/support file stays product/support merely because its
      business vocabulary says build/receipt/verify/pipeline/metrics/bootstrap;
    * a neutral-path file that was classified as machinery may be mixed-purpose, so
      only symbols with strong local machinery evidence retain a machinery role;
      its other symbols fall back to product when the parent path is clearly product
      source, otherwise to essential support.

    This makes symbol refinement a correction mechanism rather than a second loose
    keyword classifier layered on top of the first one.
    """

    # Linux-scale repositories can have hundreds or thousands of symbols in a
    # single source file. Splitting the same complete file text and re-tokenizing
    # the same path for every symbol makes refinement scale with symbols * file
    # length instead of the actual symbol snippets. Build those immutable per-file
    # views once and reuse them for every symbol in that file.
    lines_by_path = {item.component.path: item.text.splitlines() for item in scanned_files}
    path_role_by_path = {path: _path_role(path) for path in lines_by_path}
    product_context_by_path = {path: _product_context(path) for path in lines_by_path}

    for symbol in graph.symbols.values():
        if symbol.kind == SymbolKind.FILE:
            symbol.role_confidence = 1.0
            symbol.role_source = "file-classification"
            continue

        path_role = path_role_by_path.get(symbol.path)
        if path_role is not None:
            symbol.category = path_role
            symbol.role_confidence = 0.98
            symbol.role_source = "strong-path-role"
            continue

        lines = lines_by_path.get(symbol.path, ())
        start = max(0, symbol.start_line - 1)
        end = max(start + 1, min(len(lines), symbol.end_line))
        snippet = "\n".join(lines[start:end])
        best = _best_local(_score_local(symbol, snippet))

        # Product/support is sticky. Domain concepts frequently reuse machinery words,
        # so lexical evidence alone is not allowed to promote them to machinery.
        if symbol.category not in MACHINERY_CATEGORIES:
            if best is not None:
                best_category, score, second = best
                if best_category not in MACHINERY_CATEGORIES and score >= 5.0 and score - second >= 0.5:
                    symbol.category = best_category
                    symbol.role_confidence = min(0.95, 0.66 + 0.04 * score)
                    symbol.role_source = "symbol-local-product-evidence"
                    continue
            symbol.role_confidence = 0.72 if symbol.category in PRODUCT_CATEGORIES else 0.62
            symbol.role_source = "file-seed-preserved"
            continue

        # Machinery-seeded neutral files are where local refinement earns its keep.
        if best is not None:
            best_category, score, second = best
            if best_category in MACHINERY_CATEGORIES and score >= 5.0 and score - second >= 0.5:
                symbol.category = best_category
                symbol.role_confidence = min(0.97, 0.68 + 0.04 * score)
                symbol.role_source = "symbol-local-machinery-evidence"
                continue

        symbol.category = Category.CORE_PRODUCT if product_context_by_path.get(symbol.path, False) else Category.ESSENTIAL_SUPPORT
        symbol.role_confidence = 0.68 if symbol.category == Category.CORE_PRODUCT else 0.62
        symbol.role_source = "mixed-file-context-fallback"
