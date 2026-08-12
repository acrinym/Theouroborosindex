from __future__ import annotations

import ast
import json
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

from .model import Category
from .scanner import ScannedFile
from .semantic import Resolution, SemanticGraph, Symbol, SymbolKind


_PY_ROUTE_RE = re.compile(
    r"^\s*@[\w.]+\.(?P<method>get|post|put|patch|delete|options|head)\(\s*[rubfRUBF]*[\"'](?P<path>[^\"']+)"
)
_PY_GENERIC_ROUTE_RE = re.compile(
    r"^\s*@[\w.]+\.route\(\s*[rubfRUBF]*[\"'](?P<path>[^\"']+)"
)
_JS_ROUTE_RE = re.compile(
    r"\b(?:app|router|server)\.(?P<method>get|post|put|patch|delete|options|head)\(\s*[\"'](?P<path>[^\"']+)"
)
_CSHARP_ROUTE_RE = re.compile(
    r"^\s*\[(?P<method>HttpGet|HttpPost|HttpPut|HttpPatch|HttpDelete|HttpHead|HttpOptions)"
    r"(?:\(\s*[\"'](?P<path>[^\"']*)[\"'])?"
)
_JAVA_ROUTE_RE = re.compile(
    r"^\s*@(?P<method>GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)"
    r"(?:\(\s*(?:value\s*=\s*)?[\"'](?P<path>[^\"']*)[\"'])?"
)
_RUST_ROUTE_RE = re.compile(
    r'^\s*#\[(?P<method>get|post|put|patch|delete|head|options)\(\s*"(?P<path>[^"]+)"'
)
_JS_EXPORT_RE = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)"
)
_PUBLIC_DECL_RE = re.compile(r"^\s*public\b")
_RUST_PUBLIC_RE = re.compile(r"^\s*pub(?:\([^)]*\))?\s+")
_SCRIPT_VALUE_RE = re.compile(r'^\s*["\']?(?P<name>[A-Za-z0-9_.-]+)["\']?\s*=\s*["\'](?P<target>[^"\']+)["\']\s*$')


@dataclass(slots=True)
class CapabilityEvidence:
    kind: str
    path: str
    line: int
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class Capability:
    id: str
    kind: str
    name: str
    path: str
    line: int
    symbol_id: str | None
    evidence: list[CapabilityEvidence] = field(default_factory=list)
    implementation_symbols: list[dict] = field(default_factory=list)
    implementation_files: list[str] = field(default_factory=list)
    exact_relationships: list[dict] = field(default_factory=list)
    probable_relationships: int = 0
    unresolved_relationships: int = 0
    neighborhood_truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "path": self.path,
            "line": self.line,
            "symbol_id": self.symbol_id,
            "evidence": [item.to_dict() for item in self.evidence],
            "implementation_symbols": self.implementation_symbols,
            "implementation_files": self.implementation_files,
            "exact_relationships": self.exact_relationships,
            "probable_relationships": self.probable_relationships,
            "unresolved_relationships": self.unresolved_relationships,
            "neighborhood_truncated": self.neighborhood_truncated,
        }


@dataclass(slots=True)
class CapabilityAtlas:
    capabilities: list[Capability]
    warnings: list[str] = field(default_factory=list)

    @property
    def exact_anchored_count(self) -> int:
        return sum(capability.symbol_id is not None for capability in self.capabilities)

    @property
    def unanchored_count(self) -> int:
        return len(self.capabilities) - self.exact_anchored_count

    def to_dict(self) -> dict:
        return {
            "capability_count": len(self.capabilities),
            "exact_anchored_count": self.exact_anchored_count,
            "unanchored_count": self.unanchored_count,
            "warnings": self.warnings,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }


def _symbols_by_path(graph: SemanticGraph) -> dict[str, list[Symbol]]:
    result: dict[str, list[Symbol]] = {}
    for symbol in graph.symbols.values():
        result.setdefault(symbol.path, []).append(symbol)
    for symbols in result.values():
        symbols.sort(key=lambda item: (item.start_line, item.end_line - item.start_line, item.qualified_name))
    return result


def _nearest_symbol(
    symbols_by_path: dict[str, list[Symbol]],
    path: str,
    line: int,
    *,
    name: str | None = None,
    after_lines: int = 8,
) -> Symbol | None:
    symbols = [
        symbol
        for symbol in symbols_by_path.get(path, [])
        if symbol.kind not in {SymbolKind.FILE, SymbolKind.MODULE, SymbolKind.NAMESPACE}
    ]
    if name:
        exact = [symbol for symbol in symbols if symbol.name == name or symbol.qualified_name == name]
        if exact:
            return min(exact, key=lambda item: (abs(item.start_line - line), item.start_line))
    containing = [symbol for symbol in symbols if symbol.start_line <= line <= symbol.end_line]
    if containing:
        return min(containing, key=lambda item: (item.end_line - item.start_line, item.start_line))
    following = [symbol for symbol in symbols if line <= symbol.start_line <= line + after_lines]
    if following:
        return min(following, key=lambda item: (item.start_line, item.end_line - item.start_line))
    return None


def _find_module_symbol(graph: SemanticGraph, module: str, callable_name: str) -> Symbol | None:
    expected_suffix = module.replace(".", "/") + ".py"
    candidates = [
        symbol
        for symbol in graph.symbols.values()
        if symbol.path.endswith(expected_suffix)
        and (symbol.name == callable_name or symbol.qualified_name.endswith("." + callable_name))
    ]
    if len(candidates) == 1:
        return candidates[0]
    top_level = [symbol for symbol in candidates if symbol.parent_id is None]
    return top_level[0] if len(top_level) == 1 else None


def _python_exports(item: ScannedFile) -> list[tuple[str, int]]:
    if item.component.language != "python":
        return []
    try:
        tree = ast.parse(item.text)
    except (SyntaxError, ValueError, RecursionError):
        return []
    exported: list[tuple[str, int]] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = node.value
        if not isinstance(value, (ast.List, ast.Tuple)):
            continue
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                exported.append((element.value, int(getattr(element, "lineno", getattr(node, "lineno", 1)))))
    return exported


def _candidate(
    kind: str,
    name: str,
    path: str,
    line: int,
    symbol: Symbol | None,
    evidence_kind: str,
    detail: str,
) -> Capability:
    return Capability(
        id=f"{kind}:{path}:{line}:{name}",
        kind=kind,
        name=name,
        path=path,
        line=line,
        symbol_id=symbol.id if symbol else None,
        evidence=[CapabilityEvidence(evidence_kind, path, line, detail)],
    )


def _discover_explicit_surfaces(scanned_files: list[ScannedFile], graph: SemanticGraph) -> list[Capability]:
    symbols_by_path = _symbols_by_path(graph)
    found: list[Capability] = []

    for item in scanned_files:
        path = item.component.path
        lines = item.text.splitlines()
        language = item.component.language

        if PurePosixPath(path).name == "pyproject.toml":
            section = ""
            for line_number, raw in enumerate(lines, 1):
                stripped = raw.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    section = stripped[1:-1].strip()
                    continue
                if section not in {"project.scripts", "project.gui-scripts", "tool.poetry.scripts"}:
                    continue
                match = _SCRIPT_VALUE_RE.match(raw)
                if not match:
                    continue
                target = match.group("target")
                if ":" not in target:
                    continue
                module, callable_name = target.split(":", 1)
                callable_name = callable_name.split(".", 1)[0]
                symbol = _find_module_symbol(graph, module.strip(), callable_name.strip())
                found.append(_candidate(
                    "cli", match.group("name"), path, line_number, symbol,
                    "packaging-entrypoint", f"[{section}] -> {target}",
                ))

        if PurePosixPath(path).name == "package.json":
            try:
                package = json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                package = None
            if isinstance(package, dict):
                bins = package.get("bin")
                if isinstance(bins, str):
                    package_name = str(package.get("name") or PurePosixPath(path).parent.name or "package")
                    bins = {package_name: bins}
                if isinstance(bins, dict):
                    for name, target in sorted(bins.items()):
                        if not isinstance(target, str):
                            continue
                        normalized = PurePosixPath(path).parent.joinpath(target).as_posix()
                        symbol = _nearest_symbol(symbols_by_path, normalized, 1, name="main", after_lines=10_000)
                        found.append(_candidate(
                            "cli", str(name), path, 1, symbol,
                            "package-entrypoint", f"package.json bin -> {target}",
                        ))

        for line_number, raw in enumerate(lines, 1):
            match = _PY_ROUTE_RE.match(raw) if language == "python" else None
            if match:
                found.append(_candidate(
                    "http-route", f"{match.group('method').upper()} {match.group('path')}",
                    path, line_number, _nearest_symbol(symbols_by_path, path, line_number),
                    "route-declaration", raw.strip(),
                ))
                continue
            match = _PY_GENERIC_ROUTE_RE.match(raw) if language == "python" else None
            if match:
                found.append(_candidate(
                    "http-route", f"ROUTE {match.group('path')}", path, line_number,
                    _nearest_symbol(symbols_by_path, path, line_number), "route-declaration", raw.strip(),
                ))
                continue
            match = _JS_ROUTE_RE.search(raw) if language in {"javascript", "typescript", "tsx"} else None
            if match:
                found.append(_candidate(
                    "http-route", f"{match.group('method').upper()} {match.group('path')}", path, line_number,
                    _nearest_symbol(symbols_by_path, path, line_number), "route-declaration", raw.strip(),
                ))
                continue
            match = _CSHARP_ROUTE_RE.match(raw) if language == "csharp" else None
            if match:
                method = match.group("method")[4:].upper()
                route = match.group("path") or "<attribute-route>"
                found.append(_candidate(
                    "http-route", f"{method} {route}", path, line_number,
                    _nearest_symbol(symbols_by_path, path, line_number), "route-attribute", raw.strip(),
                ))
                continue
            match = _JAVA_ROUTE_RE.match(raw) if language in {"java", "kotlin"} else None
            if match:
                method = match.group("method").removesuffix("Mapping").upper() or "REQUEST"
                route = match.group("path") or "<annotation-route>"
                found.append(_candidate(
                    "http-route", f"{method} {route}", path, line_number,
                    _nearest_symbol(symbols_by_path, path, line_number), "route-annotation", raw.strip(),
                ))
                continue
            match = _RUST_ROUTE_RE.match(raw) if language == "rust" else None
            if match:
                found.append(_candidate(
                    "http-route", f"{match.group('method').upper()} {match.group('path')}", path, line_number,
                    _nearest_symbol(symbols_by_path, path, line_number), "route-attribute", raw.strip(),
                ))

        if language == "python" and "__name__" in item.text and "__main__" in item.text:
            main = _nearest_symbol(symbols_by_path, path, 1, name="main", after_lines=10_000)
            if main:
                found.append(_candidate(
                    "entrypoint", PurePosixPath(path).stem, path, main.start_line, main,
                    "python-main", "module contains an __main__ guard anchored to main()",
                ))

        if language in {"go", "java", "csharp"}:
            main_names = {"go": "main", "java": "main", "csharp": "Main"}
            main = _nearest_symbol(symbols_by_path, path, 1, name=main_names[language], after_lines=10_000)
            if main:
                start_line = lines[main.start_line - 1] if 0 < main.start_line <= len(lines) else ""
                looks_main = (
                    (language == "go" and re.search(r"\bfunc\s+main\s*\(", start_line))
                    or (language == "java" and re.search(r"\bstatic\s+void\s+main\s*\(", start_line, re.I))
                    or (language == "csharp" and re.search(r"\bstatic\b.*\bMain\s*\(", start_line))
                )
                if looks_main:
                    found.append(_candidate(
                        "entrypoint", f"{PurePosixPath(path).stem}.{main.name}", path, main.start_line, main,
                        f"{language}-main", start_line.strip(),
                    ))

        for name, line_number in _python_exports(item):
            symbol = _nearest_symbol(symbols_by_path, path, line_number, name=name, after_lines=10_000)
            if symbol:
                found.append(_candidate(
                    "public-api", name, path, line_number, symbol, "explicit-export", f"__all__ exports {name}",
                ))

        if language in {"javascript", "typescript", "tsx"}:
            for line_number, raw in enumerate(lines, 1):
                match = _JS_EXPORT_RE.match(raw)
                if not match:
                    continue
                name = match.group("name")
                found.append(_candidate(
                    "public-api", name, path, line_number,
                    _nearest_symbol(symbols_by_path, path, line_number, name=name), "explicit-export", raw.strip(),
                ))

    return found


def _discover_semantic_surfaces(
    scanned_files: list[ScannedFile],
    graph: SemanticGraph,
    already_anchored: set[str],
) -> list[Capability]:
    text_by_path = {item.component.path: item.text.splitlines() for item in scanned_files}
    found: list[Capability] = []
    for symbol in sorted(graph.symbols.values(), key=lambda item: (item.path, item.start_line, item.qualified_name)):
        if symbol.id in already_anchored:
            continue
        if symbol.kind in {SymbolKind.FILE, SymbolKind.MODULE, SymbolKind.NAMESPACE, SymbolKind.VARIABLE, SymbolKind.UNKNOWN}:
            continue
        if symbol.parent_id is not None or symbol.name.startswith("_"):
            continue

        lines = text_by_path.get(symbol.path, [])
        declaration = lines[symbol.start_line - 1].strip() if 0 < symbol.start_line <= len(lines) else ""
        explicit_public = False
        public_detail = ""
        if symbol.language in {"csharp", "java", "kotlin"} and _PUBLIC_DECL_RE.match(declaration):
            explicit_public = True
            public_detail = declaration
        elif symbol.language == "rust" and _RUST_PUBLIC_RE.match(declaration):
            explicit_public = True
            public_detail = declaration
        elif symbol.language == "go" and symbol.name[:1].isupper():
            explicit_public = True
            public_detail = f"Go exported identifier {symbol.name}"

        if explicit_public:
            found.append(_candidate(
                "public-symbol", symbol.qualified_name, symbol.path, symbol.start_line, symbol,
                "language-public-declaration", public_detail,
            ))
            continue

        if symbol.category == Category.USER_SURFACE and symbol.role_confidence >= 0.80:
            found.append(_candidate(
                "user-surface", symbol.qualified_name, symbol.path, symbol.start_line, symbol,
                "semantic-role", f"{symbol.role_source}; confidence={symbol.role_confidence:.2f}",
            ))
    return found


def _decorate_neighborhood(
    capability: Capability,
    graph: SemanticGraph,
    *,
    adjacency: dict[str, list],
    max_depth: int,
    max_symbols: int,
) -> None:
    if not capability.symbol_id or capability.symbol_id not in graph.symbols:
        return

    visited = {capability.symbol_id}
    queue = deque([(capability.symbol_id, 0)])
    exact_relationships: list[dict] = []
    probable = 0
    unresolved = 0
    truncated = False

    while queue:
        source_id, depth = queue.popleft()
        for edge in adjacency.get(source_id, []):
            if edge.resolution == Resolution.PROBABLE:
                probable += 1
                continue
            if edge.resolution == Resolution.UNRESOLVED:
                unresolved += 1
                continue
            if edge.resolution != Resolution.EXACT or edge.target_id is None:
                continue
            exact_relationships.append({
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "kind": edge.kind.value,
                "evidence": edge.evidence,
            })
            if depth >= max_depth or edge.target_id in visited:
                continue
            if len(visited) >= max_symbols:
                truncated = True
                continue
            visited.add(edge.target_id)
            queue.append((edge.target_id, depth + 1))

    symbols = [graph.symbols[symbol_id] for symbol_id in visited if symbol_id in graph.symbols]
    symbols.sort(key=lambda item: (item.path, item.start_line, item.qualified_name))
    capability.implementation_symbols = [
        {
            "id": symbol.id,
            "name": symbol.name,
            "qualified_name": symbol.qualified_name,
            "path": symbol.path,
            "language": symbol.language,
            "kind": symbol.kind.value,
            "category": symbol.category.value,
            "start_line": symbol.start_line,
            "end_line": symbol.end_line,
            "value_distance": symbol.value_distance,
            "role_confidence": symbol.role_confidence,
            "role_source": symbol.role_source,
        }
        for symbol in symbols
    ]
    capability.implementation_files = sorted({symbol.path for symbol in symbols})
    capability.exact_relationships = sorted(
        exact_relationships,
        key=lambda item: (item["source_id"], item["target_id"], item["kind"], item["evidence"]),
    )
    capability.probable_relationships = probable
    capability.unresolved_relationships = unresolved
    capability.neighborhood_truncated = truncated


def build_capability_atlas(
    scanned_files: list[ScannedFile],
    graph: SemanticGraph,
    *,
    max_capabilities: int = 200,
    max_depth: int = 4,
    max_symbols_per_capability: int = 250,
) -> CapabilityAtlas:
    explicit = _discover_explicit_surfaces(scanned_files, graph)
    anchored = {item.symbol_id for item in explicit if item.symbol_id}
    candidates = explicit + _discover_semantic_surfaces(scanned_files, graph, anchored)

    unique: dict[tuple[str, str, str, int], Capability] = {}
    for capability in candidates:
        key = (capability.kind, capability.name, capability.path, capability.line)
        existing = unique.get(key)
        if existing is None:
            unique[key] = capability
        else:
            existing.evidence.extend(capability.evidence)
            if existing.symbol_id is None and capability.symbol_id is not None:
                existing.symbol_id = capability.symbol_id

    ordered = sorted(unique.values(), key=lambda item: (item.kind, item.name.lower(), item.path, item.line))
    warnings: list[str] = []
    if len(ordered) > max_capabilities:
        warnings.append(
            f"Capability discovery found {len(ordered)} surfaces; showing the first {max_capabilities} deterministically."
        )
        ordered = ordered[:max_capabilities]

    adjacency: dict[str, list] = {}
    for edge in graph.edges:
        adjacency.setdefault(edge.source_id, []).append(edge)

    for capability in ordered:
        _decorate_neighborhood(
            capability,
            graph,
            adjacency=adjacency,
            max_depth=max_depth,
            max_symbols=max_symbols_per_capability,
        )
        if capability.neighborhood_truncated:
            warnings.append(
                f"Implementation neighborhood for {capability.name!r} reached the {max_symbols_per_capability}-symbol bound."
            )

    if not ordered:
        warnings.append(
            "No explicit or high-confidence user-facing capability surfaces were found. "
            "This is an absence of supported static evidence, not proof that the software has no capabilities."
        )
    elif any(item.symbol_id is None for item in ordered):
        warnings.append(
            "Some surfaces could not be anchored to a semantic symbol. Their declarations remain visible, "
            "but no implementation neighborhood is inferred for them."
        )

    return CapabilityAtlas(capabilities=ordered, warnings=warnings)
