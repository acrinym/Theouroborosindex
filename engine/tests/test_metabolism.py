from __future__ import annotations

import json
import subprocess
from pathlib import Path

import ouroboros.metabolism_cli as metabolism_cli_module
from ouroboros.metabolism import scan_repository_metabolism
from ouroboros.metabolism_report import build_metabolism_report_html


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir()
    _git(path, "init", "-b", "main", "--template=")
    _git(path, "config", "user.name", "Ouroboros Test")
    _git(path, "config", "user.email", "ouroboros@example.invalid")
    _git(path, "config", "commit.gpgsign", "false")
    _git(path, "config", "tag.gpgsign", "false")
    _git(path, "config", "core.hooksPath", str(path / ".git" / "no-hooks"))
    return path


def _commit(repo: Path, subject: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", subject)
    return _git(repo, "rev-parse", "HEAD")


def test_metabolism_tracks_absolute_mass_last_use_and_superseded_candidates_without_execution(tmp_path: Path):
    repo = _init_repo(tmp_path / "repo")
    marker = tmp_path / "TARGET_WAS_EXECUTED"
    (repo / "src").mkdir()
    (repo / "tools").mkdir()
    (repo / "src" / "app.py").write_text(
        "from tools.stage_release120 import stage\n"
        "def main():\n"
        "    return stage()\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    (repo / "tools" / "stage_release120.py").write_text(
        "from pathlib import Path\n"
        f"MARKER = Path({str(marker)!r})\n"
        "def stage():\n"
        "    MARKER.write_text('executed')\n"
        "    return 120\n",
        encoding="utf-8",
    )
    (repo / "tools" / "lonely_tool.py").write_text("def lonely():\n    return 'unused'\n", encoding="utf-8")
    first = _commit(repo, "release 120 machinery")

    (repo / "tools" / "stage_release121.py").write_text("def stage():\n    return 121\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text(
        "from tools.stage_release121 import stage\n"
        "def main():\n"
        "    return stage()\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )
    _commit(repo, "move to release 121 machinery")

    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "release.yml").write_text(
        "name: release\nrun-name: tools/stage_release121.py\n",
        encoding="utf-8",
    )
    third = _commit(repo, "wire current release workflow")

    result = scan_repository_metabolism(repo, from_ref=first, to_ref=third, max_commits=3)
    assert not marker.exists()
    assert result["range"]["commits_scanned"] == 3
    assert result["range"]["sampled"] is False
    assert result["policy"]["target_execution"] is False
    assert result["policy"]["deletion_recommendation"] is False
    assert "machinery_lines" in result["mass"]["current"]
    assert "machinery_share" in result["mass"]["current"]

    rows = {row["path"]: row for row in result["files"]}
    old = rows["tools/stage_release120.py"]
    assert old["status"] == "superseded-candidate"
    assert "tools/stage_release121.py" in old["newer_version_family_siblings"]
    assert old["last_observed_use"]["sha"] == first

    current = rows["tools/stage_release121.py"]
    assert current["status"] == "active"
    assert any(
        key in current["current_use"]["kinds"]
        for key in ("local_dependency_inbound", "exact_semantic_inbound", "static_path_references")
    )

    lonely = rows["tools/lonely_tool.py"]
    assert lonely["status"] == "bounded-orphan-candidate"
    assert lonely["last_observed_use"] is None
    assert lonely["last_observed_change"] is None


def test_metabolism_report_is_self_contained_and_preserves_evidence_boundary():
    result = {
        "mass": {
            "start": {"machinery_lines": 10, "machinery_share": 0.5, "product_lines": 5, "product_share": 0.25},
            "current": {"machinery_lines": 12, "machinery_share": 0.4, "product_lines": 12, "product_share": 0.4},
            "delta": {"machinery_lines": 2, "machinery_share": -0.1, "product_lines": 7, "product_share": 0.15},
        },
        "status_counts": {"dormant": 1},
        "frames": [{"sha": "a" * 40, "subject": "one", "machinery_lines": 10, "machinery_share": 0.5, "product_lines": 5, "product_share": 0.25}],
        "files": [{
            "path": "tools/old.py", "status": "dormant", "purpose": "developer-tooling", "code_lines": 10,
            "last_observed_use": {"sha": "a" * 40, "subject": "one"},
            "current_use": {"kinds": []}, "newer_version_family_siblings": [],
            "status_evidence": ["bounded evidence"],
        }],
    }
    report = build_metabolism_report_html(result)
    assert "Repository Metabolism / Dormancy Atlas" in report
    assert "10 → 12 lines (+2)" in report
    assert "falling machinery percentage does not mean machinery shrank" in report
    assert "application/octet-stream" in report
    assert "does not recommend deletion" in report
    assert "<script src=" not in report.lower()


def test_metabolism_cli_writes_json_and_report(tmp_path: Path, monkeypatch):
    result = {
        "repository": "/tmp/repo",
        "range": {"commits_scanned": 2},
        "policy": {"target_execution": False},
        "mass": {
            "start": {"machinery_lines": 10, "machinery_share": 0.5, "product_lines": 5, "product_share": 0.25},
            "current": {"machinery_lines": 12, "machinery_share": 0.4, "product_lines": 12, "product_share": 0.4},
            "delta": {"machinery_lines": 2, "machinery_share": -0.1, "product_lines": 7, "product_share": 0.15},
        },
        "status_counts": {"active": 1},
        "frames": [],
        "files": [],
    }
    monkeypatch.setattr(metabolism_cli_module, "scan_repository_metabolism", lambda *args, **kwargs: result)
    output = tmp_path / "metabolism.json"
    report = tmp_path / "metabolism.html"
    assert metabolism_cli_module.main([".", "--since", "2", "--json", str(output), "--report", str(report), "--quiet"]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["mass"]["current"]["machinery_lines"] == 12
    assert "Repository Metabolism" in report.read_text(encoding="utf-8")
