from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ouroboros.drivers import change_drivers
from ouroboros.drivers_cli import main as drivers_main
from ouroboros.drivers_report import build_drivers_report_html


def _payload(components: list[dict], counts: dict[str, int], depth: int = 1) -> dict:
    return {
        "analyzer": {"version": "0.9.0", "source_sha": "a" * 40},
        "repository": "/repo",
        "repository_identity": {"git_sha": "b" * 40},
        "scan": {"canonical": True},
        "baseline": {
            "metrics": {
                "direct_product_share": 0.5,
                "tooling_share": 0.5,
                "scaffolding_ratio": 1.0,
                "category_code_lines": counts,
            },
            "components": components,
            "directory_profiles": [],
        },
        "semantic": {
            "metrics": {"relationship_count": 1, "exact_resolution_rate": 1.0, "max_recursive_depth": depth, "semantic_ouroboros_index": depth * 10.0},
            "chains": [],
        },
    }


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-b", "main", "--template=")
    _git(path, "config", "user.name", "Ouroboros Test")
    _git(path, "config", "user.email", "ouroboros@example.invalid")
    _git(path, "config", "commit.gpgsign", "false")
    _git(path, "config", "core.hooksPath", str(path / ".git" / "no-hooks"))
    return path


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_change_drivers_rank_added_removed_and_recategorized_files():
    before = _payload(
        [
            {"path": "src/app.py", "category": "core-product", "code_lines": 100},
            {"path": "old.py", "category": "core-product", "code_lines": 20},
        ],
        {"core-product": 120},
    )
    after = _payload(
        [
            {"path": "src/app.py", "category": "testing", "code_lines": 100},
            {"path": "tests/test_app.py", "category": "testing", "code_lines": 40},
        ],
        {"testing": 140},
        depth=2,
    )
    result = change_drivers(before, after)
    assert [row["path"] for row in result["files"]][:3] == ["src/app.py", "tests/test_app.py", "old.py"]
    assert result["files"][0]["status"] == "recategorized"
    assert result["categories"][0]["category"] in {"core-product", "testing"}
    assert "quality score" in result["semantics"]


def test_driver_report_is_self_contained_and_escapes_paths():
    result = {
        "before": {"sha": "1" * 40},
        "after": {"sha": "2" * 40},
        "drivers": {
            "files": [{"path": "<script>.py", "status": "added", "before_category": None, "after_category": "testing", "before_code_lines": 0, "after_code_lines": 4, "delta_code_lines": 4}],
            "categories": [],
            "structural_explanations": [],
            "deepest_exact_chains": {},
        },
    }
    text = build_drivers_report_html(result)
    assert "&lt;script&gt;.py" in text
    assert "<script>.py" not in text
    assert "https://" not in text.lower()
    assert "<script src=" not in text.lower()


def test_drivers_cli_scans_two_refs_without_executing_target(tmp_path: Path):
    repo = _repo(tmp_path / "repo")
    marker = tmp_path / "EXECUTED"
    (repo / "app.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\ndef value(): return 1\n", encoding="utf-8")
    first = _commit(repo, "product")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_app.py").write_text("def test_value(): assert 1 == 1\n" * 20, encoding="utf-8")
    second = _commit(repo, "tests")
    output = tmp_path / "drivers.json"
    report = tmp_path / "drivers.html"
    assert drivers_main([str(repo), "--before", first, "--after", second, "--json", str(output), "--report", str(report), "--quiet"]) == 0
    assert not marker.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["scan_policy"]["target_execution"] is False
    assert payload["scan_policy"]["snapshots_scanned"] == 2
    assert any(row["path"] == "tests/test_app.py" for row in payload["drivers"]["files"])
    assert report.exists()
