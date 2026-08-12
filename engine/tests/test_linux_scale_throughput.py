from __future__ import annotations

import json

import ouroboros.analyze as analyze_module
import ouroboros.cli as cli_module
import ouroboros.scanner as scanner_module
from ouroboros.model import Category, Component
from ouroboros.scanner import ScannedFile
from ouroboros.semantic.model import SemanticGraph, Symbol, SymbolKind
from ouroboros.semantic.roles import _snippet_prefix, refine_symbol_categories


def test_canonical_scan_reads_repository_once(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "def greet(name):\n"
        "    return f'hello {name}'\n\n"
        "def main():\n"
        "    return greet('world')\n",
        encoding="utf-8",
    )

    real_scan_repository = cli_module.scan_repository
    calls = 0

    def counting_scan_repository(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_scan_repository(*args, **kwargs)

    # Before the Linux-scale throughput fix, cli.scan() called analyze_repository()
    # (which scanned once) and then scan_repository() again for semantics. Count
    # both import sites so this regression test would catch that duplicate pass.
    monkeypatch.setattr(cli_module, "scan_repository", counting_scan_repository)
    monkeypatch.setattr(analyze_module, "scan_repository", counting_scan_repository)

    baseline, semantic = cli_module.scan(repo, use_repo_config=False)

    assert calls == 1
    assert len(baseline.components) == 1
    assert semantic.metrics is not None
    assert semantic.metrics.symbol_count >= 2


def test_scanner_reuses_one_line_view_per_file(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "driver.c").write_text(
        "/* driver */\n"
        "#include <linux/types.h>\n"
        "int answer(void) { return 42; }\n",
        encoding="utf-8",
    )

    real_looks_generated = scanner_module._looks_generated
    real_code_lines = scanner_module._code_lines
    observed_line_views: list[int] = []

    def observing_looks_generated(text, lines=None):
        assert lines is not None
        observed_line_views.append(id(lines))
        return real_looks_generated(text, lines)

    def observing_code_lines(text, language, lines=None):
        assert lines is not None
        observed_line_views.append(id(lines))
        return real_code_lines(text, language, lines)

    monkeypatch.setattr(scanner_module, "_looks_generated", observing_looks_generated)
    monkeypatch.setattr(scanner_module, "_code_lines", observing_code_lines)

    scanned = scanner_module.scan_repository(repo)

    assert len(scanned) == 1
    assert len(observed_line_views) == 2
    assert observed_line_views[0] == observed_line_views[1]
    assert scanned[0].component.lines == 3
    assert scanned[0].component.code_lines == 2


class _CountingText(str):
    def __new__(cls, value: str):
        instance = super().__new__(cls, value)
        instance.split_calls = 0
        return instance

    def splitlines(self, *args, **kwargs):
        self.split_calls += 1
        return super().splitlines(*args, **kwargs)


def test_symbol_role_refinement_splits_each_file_once() -> None:
    text = _CountingText("\n".join(f"line_{index} = {index}" for index in range(1, 201)))
    component = Component(
        path="src/domain.py",
        language="python",
        lines=200,
        code_lines=200,
        bytes=len(text.encode("utf-8")),
        category=Category.CORE_PRODUCT,
    )
    scanned = ScannedFile(component=component, text=text)
    graph = SemanticGraph()
    graph.add_symbols([
        Symbol(
            id="src/domain.py::<file>",
            path="src/domain.py",
            language="python",
            kind=SymbolKind.FILE,
            name="domain.py",
            qualified_name="src/domain.py",
            start_line=1,
            end_line=200,
            category=Category.CORE_PRODUCT,
        ),
        *[
            Symbol(
                id=f"src/domain.py::symbol_{index}@{index}",
                path="src/domain.py",
                language="python",
                kind=SymbolKind.FUNCTION,
                name=f"symbol_{index}",
                qualified_name=f"symbol_{index}",
                start_line=index,
                end_line=index,
                category=Category.CORE_PRODUCT,
            )
            for index in range(1, 101)
        ],
    ])

    refine_symbol_categories(graph, [scanned])

    # The file text is materialized into lines once, regardless of symbol count.
    # The previous implementation split the complete 200-line file once per symbol.
    assert text.split_calls == 1


def test_role_snippet_prefix_preserves_previous_4000_character_view() -> None:
    lines = [
        "alpha " + ("a" * 2500),
        "beta " + ("b" * 2500),
        "gamma " + ("c" * 2500),
    ]

    assert _snippet_prefix(lines, 0, len(lines)) == "\n".join(lines)[:4000]
    assert _snippet_prefix(lines, 1, len(lines)) == "\n".join(lines[1:])[:4000]


def test_timings_json_checkpoints_real_scan_progress(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "class Greeter:\n"
        "    def greet(self, name):\n"
        "        return name.upper()\n",
        encoding="utf-8",
    )
    timings_path = tmp_path / "timings.json"
    output_path = tmp_path / "scan.json"

    result = cli_module.main([
        str(repo),
        "--canonical",
        "--quiet",
        "--timings-json",
        str(timings_path),
        "--json",
        str(output_path),
    ])

    assert result == 0
    timings = json.loads(timings_path.read_text(encoding="utf-8"))
    assert timings["status"] == "complete"
    assert timings["stage"] == "complete"
    assert timings["scanned_files"] == 1
    assert timings["semantic_files_total"] == 1
    assert timings["semantic_files_parsed"] == 1
    assert timings["semantic_stage"] == "complete"
    assert timings["repository_scan_seconds"] >= 0.0
    assert timings["baseline_analysis_seconds"] >= 0.0
    assert timings["semantic_total_seconds"] >= 0.0
    assert timings["json_write_seconds"] >= 0.0
    assert output_path.exists()


def test_timings_write_failure_is_reported_once(tmp_path, monkeypatch, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    writes = 0

    def fail_write_timings(*args, **kwargs):
        nonlocal writes
        writes += 1
        raise OSError("timing volume unavailable")

    monkeypatch.setattr(cli_module, "_write_timings", fail_write_timings)

    result = cli_module.main([
        str(repo),
        "--canonical",
        "--quiet",
        "--timings-json",
        str(tmp_path / "timings.json"),
    ])

    captured = capsys.readouterr()
    assert result == 2
    assert writes == 1
    assert "could not write timings" in captured.out.lower()
    assert "timing volume unavailable" in captured.out
