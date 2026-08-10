from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Protocol

from ouroboros.model import Category
from ouroboros.scanner import ScannedFile

from .model import EdgeKind, ParseDiagnostic, ParsedUnit, Resolution, SemanticEdge, Symbol, SymbolKind


def _file_id(path: str) -> str:
    return f"{path}::<file>"


def _symbol_id(path: str, qualified_name: str, line: int) -> str:
    return f"{path}::{qualified_name}@{line}"


def _category(item: ScannedFile) -> Category:
    return item.component.category


class LanguageAdapter(Protocol):
    def supports(self, language: str) -> bool: ...
    def parse(self, item: ScannedFile) -> ParsedUnit: ...


class PythonAstAdapter:
    def supports(self, language: str) -> bool:
        return language == "python"

    def parse(self, item: ScannedFile) -> ParsedUnit:
        unit = ParsedUnit(path=item.component.path, language=item.component.language)
        file_symbol = Symbol(
            id=_file_id(item.component.path), path=item.component.path,
            language=item.component.language, kind=SymbolKind.FILE,
            name=item.component.path.rsplit("/", 1)[-1], qualified_name=item.component.path,
            start_line=1, end_line=max(1, item.component.lines), category=_category(item),
        )
        unit.symbols.append(file_symbol)
        try:
            tree = ast.parse(item.text, filename=item.component.path)
        except SyntaxError as exc:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language="python",
                message=f"Python AST parse failed at line {exc.lineno}: {exc.msg}",
            ))
            return unit
        except (ValueError, RecursionError) as exc:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language="python",
                message=f"Python AST parse failed: {type(exc).__name__}: {exc}",
            ))
            return unit

        visitor = _PythonVisitor(item, unit, file_symbol.id)
        try:
            visitor.visit(tree)
        except RecursionError as exc:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language="python",
                message=f"Python AST traversal depth exceeded: {exc}",
            ))
        return unit


@dataclass
class _Scope:
    symbol_id: str
    qualified_name: str
    kind: SymbolKind


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, item: ScannedFile, unit: ParsedUnit, file_symbol_id: str) -> None:
        self.item = item
        self.unit = unit
        self.scopes: list[_Scope] = [_Scope(file_symbol_id, "", SymbolKind.FILE)]
        self.import_bindings: dict[str, str] = {}

    @property
    def scope(self) -> _Scope:
        return self.scopes[-1]

    def _qualify(self, name: str) -> str:
        return f"{self.scope.qualified_name}.{name}".strip(".")

    def _add_symbol(self, node: ast.AST, name: str, kind: SymbolKind) -> Symbol:
        qualified = self._qualify(name)
        line = int(getattr(node, "lineno", 1) or 1)
        end = int(getattr(node, "end_lineno", line) or line)
        symbol = Symbol(
            id=_symbol_id(self.item.component.path, qualified, line),
            path=self.item.component.path, language="python", kind=kind,
            name=name, qualified_name=qualified, start_line=line, end_line=end,
            parent_id=self.scope.symbol_id, category=_category(self.item),
        )
        self.unit.symbols.append(symbol)
        self.unit.edges.append(SemanticEdge(
            source_id=self.scope.symbol_id, kind=EdgeKind.CONTAINS,
            target_name=qualified, target_id=symbol.id, resolution=Resolution.EXACT,
            evidence="python AST lexical containment",
        ))
        return symbol

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parent_kind = self.scope.kind
        kind = SymbolKind.METHOD if parent_kind in {
            SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.STRUCT, SymbolKind.TYPE
        } else SymbolKind.FUNCTION
        if node.name == "__init__" and kind == SymbolKind.METHOD:
            kind = SymbolKind.CONSTRUCTOR
        symbol = self._add_symbol(node, node.name, kind)
        self.scopes.append(_Scope(symbol.id, symbol.qualified_name, symbol.kind))
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        symbol = self._add_symbol(node, node.name, SymbolKind.CLASS)
        for base in node.bases:
            target = self._bound_name(_python_expr_name(base))
            if target:
                self.unit.edges.append(SemanticEdge(
                    source_id=symbol.id, kind=EdgeKind.INHERITS, target_name=target,
                    evidence="python AST class base",
                ))
        self.scopes.append(_Scope(symbol.id, symbol.qualified_name, symbol.kind))
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local = alias.asname or alias.name.split(".", 1)[0]
            self.import_bindings[local] = alias.name
            self.unit.edges.append(SemanticEdge(
                source_id=_file_id(self.item.component.path), kind=EdgeKind.IMPORTS,
                target_name=alias.name, evidence="python AST import",
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        self.unit.edges.append(SemanticEdge(
            source_id=_file_id(self.item.component.path), kind=EdgeKind.IMPORTS,
            target_name=module or ".", evidence="python AST from-import",
        ))
        if node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                self.import_bindings[local] = f"{node.module}.{alias.name}"

    def _bound_name(self, target: str | None) -> str | None:
        if not target:
            return target
        head, sep, tail = target.partition(".")
        bound = self.import_bindings.get(head)
        if not bound:
            return target
        return bound + (f".{tail}" if sep else "")

    def visit_Call(self, node: ast.Call) -> None:
        target = self._bound_name(_python_expr_name(node.func))
        if target:
            self.unit.edges.append(SemanticEdge(
                source_id=self.scope.symbol_id, kind=EdgeKind.CALLS,
                target_name=target,
                evidence="python AST call" + (" with import binding" if "." in target else ""),
            ))
        self.generic_visit(node)


def _python_expr_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _python_expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _python_expr_name(node.value)
    if isinstance(node, ast.Call):
        return _python_expr_name(node.func)
    return None


TREE_SITTER_LANGUAGE_KEYS = {
    "javascript": "javascript", "typescript": "typescript", "tsx": "tsx",
    "csharp": "csharp", "fsharp": "fsharp", "java": "java", "kotlin": "kotlin",
    "go": "go", "rust": "rust", "ruby": "ruby", "php": "php", "c": "c",
    "cpp": "cpp", "swift": "swift", "lua": "lua", "powershell": "powershell",
    "shell": "bash",
}

_DECLARATION_HINTS = (
    "class", "interface", "struct", "record", "enum", "trait", "namespace", "module",
    "function", "method", "constructor", "property",
)
_DECLARATION_ENDINGS = ("declaration", "definition", "item", "specifier")
_CALL_TYPES = {
    "call", "call_expression", "function_call_expression", "invocation_expression",
    "method_invocation", "member_call_expression", "command_invocation",
}
_IMPORT_NODE_TYPES = {
    "import_statement", "import_declaration", "using_directive", "use_declaration",
    "preproc_include", "include_statement", "open_declaration",
}


class TreeSitterAdapter:
    MAX_WALK_DEPTH = 400

    def supports(self, language: str) -> bool:
        return language in TREE_SITTER_LANGUAGE_KEYS

    def parse(self, item: ScannedFile) -> ParsedUnit:
        unit = ParsedUnit(path=item.component.path, language=item.component.language)
        file_symbol = Symbol(
            id=_file_id(item.component.path), path=item.component.path,
            language=item.component.language, kind=SymbolKind.FILE,
            name=item.component.path.rsplit("/", 1)[-1], qualified_name=item.component.path,
            start_line=1, end_line=max(1, item.component.lines), category=_category(item),
        )
        unit.symbols.append(file_symbol)
        try:
            from tree_sitter_language_pack import get_parser
            parser = get_parser(TREE_SITTER_LANGUAGE_KEYS[item.component.language])
            source = item.text.encode("utf-8")
            tree = parser.parse(source)
        except Exception as exc:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language=item.component.language,
                message=f"tree-sitter parser unavailable: {type(exc).__name__}: {exc}",
            ))
            return unit

        if tree.root_node.has_error:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language=item.component.language,
                message="tree-sitter parsed the file with syntax errors; partial graph retained",
            ))
        depth_flag = [False]
        try:
            self._walk(item, source, tree.root_node, unit, file_symbol, 0, depth_flag)
        except RecursionError as exc:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language=item.component.language,
                message=f"tree-sitter traversal recursion limit reached: {exc}",
            ))
        if depth_flag[0]:
            unit.diagnostics.append(ParseDiagnostic(
                path=item.component.path, language=item.component.language,
                message=f"tree-sitter traversal truncated at depth {self.MAX_WALK_DEPTH}", severity="info",
            ))
        return unit

    def _walk(self, item: ScannedFile, source: bytes, node, unit: ParsedUnit, scope: Symbol, depth: int, depth_flag: list[bool]) -> None:
        if depth >= self.MAX_WALK_DEPTH:
            depth_flag[0] = True
            return
        node_type = node.type.lower()

        if self._is_import(node_type):
            text = _node_text(source, node).strip()
            if text:
                unit.edges.append(SemanticEdge(
                    source_id=_file_id(item.component.path), kind=EdgeKind.IMPORTS,
                    target_name=_compact_reference(text), evidence=f"tree-sitter {node.type}",
                ))
            return

        if self._is_call(node_type):
            target_node = (
                node.child_by_field_name("function") or node.child_by_field_name("name")
                or node.child_by_field_name("method") or node.child_by_field_name("member")
            )
            if target_node is None:
                target_node = _first_named_child(node)
            target = _node_text(source, target_node).strip() if target_node is not None else ""
            if target:
                unit.edges.append(SemanticEdge(
                    source_id=scope.id, kind=EdgeKind.CALLS,
                    target_name=_compact_reference(target), evidence=f"tree-sitter {node.type}",
                ))

        kind = self._declaration_kind(node_type)
        if kind is not None:
            name_node = node.child_by_field_name("name")
            if name_node is None:
                name_node = _first_identifier_child(node)
            name = _node_text(source, name_node).strip() if name_node is not None else ""
            if name:
                qualified = f"{scope.qualified_name}.{name}" if scope.kind != SymbolKind.FILE else name
                line = int(node.start_point[0]) + 1
                end = int(node.end_point[0]) + 1
                symbol = Symbol(
                    id=_symbol_id(item.component.path, qualified, line), path=item.component.path,
                    language=item.component.language, kind=kind, name=name,
                    qualified_name=qualified, start_line=line, end_line=end,
                    parent_id=scope.id, category=_category(item),
                )
                unit.symbols.append(symbol)
                unit.edges.append(SemanticEdge(
                    source_id=scope.id, kind=EdgeKind.CONTAINS, target_name=qualified,
                    target_id=symbol.id, resolution=Resolution.EXACT,
                    evidence=f"tree-sitter {node.type} containment",
                ))
                self._add_bases(source, node, unit, symbol)
                for child in node.named_children:
                    self._walk(item, source, child, unit, symbol, depth + 1, depth_flag)
                return

        for child in node.named_children:
            self._walk(item, source, child, unit, scope, depth + 1, depth_flag)

    @staticmethod
    def _is_call(node_type: str) -> bool:
        return node_type in _CALL_TYPES or node_type.endswith("call_expression") or node_type.endswith("invocation")

    @staticmethod
    def _is_import(node_type: str) -> bool:
        return node_type in _IMPORT_NODE_TYPES

    @staticmethod
    def _declaration_kind(node_type: str) -> SymbolKind | None:
        if not any(node_type.endswith(ending) for ending in _DECLARATION_ENDINGS):
            return None
        if not any(hint in node_type for hint in _DECLARATION_HINTS):
            return None
        if "namespace" in node_type:
            return SymbolKind.NAMESPACE
        if "module" in node_type:
            return SymbolKind.MODULE
        if "interface" in node_type:
            return SymbolKind.INTERFACE
        if "struct" in node_type or "record" in node_type:
            return SymbolKind.STRUCT
        if "enum" in node_type:
            return SymbolKind.ENUM
        if "trait" in node_type:
            return SymbolKind.TRAIT
        if "class" in node_type:
            return SymbolKind.CLASS
        if "constructor" in node_type:
            return SymbolKind.CONSTRUCTOR
        if "method" in node_type:
            return SymbolKind.METHOD
        if "property" in node_type:
            return SymbolKind.PROPERTY
        if "function" in node_type:
            return SymbolKind.FUNCTION
        return SymbolKind.TYPE

    @staticmethod
    def _add_bases(source: bytes, node, unit: ParsedUnit, symbol: Symbol) -> None:
        for field in ("superclass", "base", "bases", "interfaces"):
            base = node.child_by_field_name(field)
            if base is None:
                continue
            text = _node_text(source, base).strip()
            if text:
                unit.edges.append(SemanticEdge(
                    source_id=symbol.id,
                    kind=EdgeKind.IMPLEMENTS if field == "interfaces" else EdgeKind.INHERITS,
                    target_name=_compact_reference(text), evidence=f"tree-sitter field {field}",
                ))


def _node_text(source: bytes, node) -> str:
    if node is None:
        return ""
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _first_named_child(node):
    for child in node.named_children:
        return child
    return None


def _first_identifier_child(node):
    for child in node.named_children:
        lowered = child.type.lower()
        if "identifier" in lowered or lowered in {"name", "type_identifier"}:
            return child
        if child.start_byte < node.start_byte + 256:
            nested = _first_identifier_child(child)
            if nested is not None:
                return nested
    return None


def _compact_reference(text: str) -> str:
    text = " ".join(text.replace("\n", " ").split())
    return text[:177] + "..." if len(text) > 180 else text


class AdapterRegistry:
    def __init__(self, adapters: list[LanguageAdapter] | None = None) -> None:
        self.adapters = adapters or [PythonAstAdapter(), TreeSitterAdapter()]

    def adapter_for(self, language: str) -> LanguageAdapter | None:
        for adapter in self.adapters:
            if adapter.supports(language):
                return adapter
        return None

    @property
    def supported_languages(self) -> set[str]:
        languages = {"python"}
        languages.update(TREE_SITTER_LANGUAGE_KEYS)
        return languages
