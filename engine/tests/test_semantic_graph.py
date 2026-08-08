from ouroboros.model import Category, Component
from ouroboros.scanner import ScannedFile
from ouroboros.semantic import EdgeKind, Resolution, SymbolKind, build_semantic_graph


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


def test_python_symbols_calls_and_value_distance():
    files = [
        scanned("app.py", """
from physics import resolve
class Player:
    def move(self):
        return resolve()
""", Category.CORE_PRODUCT),
        scanned("physics.py", """
def resolve():
    return 1
""", Category.ESSENTIAL_SUPPORT),
        scanned("verify.py", """
from app import Player
def validate():
    return Player().move()
""", Category.VERIFICATION),
        scanned("audit.py", """
from verify import validate
def record_validation():
    return validate()
""", Category.AUDIT_PROVENANCE),
    ]
    graph = build_semantic_graph(files)
    names = {symbol.qualified_name: symbol for symbol in graph.symbols.values()}
    assert names["Player"].kind == SymbolKind.CLASS
    assert names["Player.move"].kind == SymbolKind.METHOD
    assert names["resolve"].value_distance is not None
    call_edges = [edge for edge in graph.edges if edge.kind == EdgeKind.CALLS]
    assert any(edge.target_name == "resolve" and edge.resolution == Resolution.EXACT for edge in call_edges)
    assert graph.metrics is not None
    assert graph.metrics.symbol_count >= 5
    assert graph.metrics.max_recursive_depth >= 2


def test_unresolved_dynamic_target_is_retained_not_invented():
    graph = build_semantic_graph([
        scanned("app.py", """
def run(obj, name):
    return getattr(obj, name)()
""", Category.CORE_PRODUCT)
    ])
    calls = [edge for edge in graph.edges if edge.kind == EdgeKind.CALLS]
    assert any(edge.target_name == "getattr" and edge.resolution == Resolution.UNRESOLVED for edge in calls)


def test_csharp_tree_sitter_extracts_real_type_method_and_call():
    graph = build_semantic_graph([
        scanned("Game/Player.cs", """
namespace Game;
public class Player {
    public void Move() { Physics.Resolve(); }
}
public static class Physics {
    public static void Resolve() { }
}
""", Category.CORE_PRODUCT, "csharp")
    ])
    symbols = list(graph.symbols.values())
    assert any(symbol.kind == SymbolKind.CLASS and symbol.name == "Player" for symbol in symbols)
    assert any(symbol.kind == SymbolKind.METHOD and symbol.name == "Move" for symbol in symbols)
    assert any(edge.kind == EdgeKind.CALLS and "Resolve" in edge.target_name for edge in graph.edges)


def test_major_tree_sitter_adapters_emit_symbols():
    samples = {
        "javascript": "function run() { helper(); } function helper() {}",
        "typescript": "class App { run(): void { helper(); } } function helper(): void {}",
        "java": "class App { void run() { helper(); } void helper() {} }",
        "go": "package main\nfunc run(){ helper() }\nfunc helper(){}",
        "rust": "fn run(){ helper(); } fn helper(){}",
        "cpp": "void helper(){} void run(){ helper(); }",
    }
    for language, text in samples.items():
        graph = build_semantic_graph([scanned(f"sample.{language}", text, Category.CORE_PRODUCT, language)])
        non_files = [symbol for symbol in graph.symbols.values() if symbol.kind != SymbolKind.FILE]
        assert non_files, f"expected symbols for {language}"
