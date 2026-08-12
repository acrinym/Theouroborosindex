from __future__ import annotations

import subprocess
from pathlib import Path

from ouroboros.metabolism import scan_repository_metabolism


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


def test_workflow_reachable_scripts_propagate_literal_use_without_reviving_dead_cycles(tmp_path: Path):
    repo = _init_repo(tmp_path / "repo")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "tools").mkdir()
    (repo / "src").mkdir()

    (repo / ".github" / "workflows" / "release.yml").write_text(
        "name: release\nsteps:\n  - run: bash tools/release.sh\n",
        encoding="utf-8",
    )
    (repo / "tools" / "release.sh").write_text(
        "#!/usr/bin/env bash\npython helper.py\npython ../src/postprocess.py\n",
        encoding="utf-8",
    )
    (repo / "tools" / "helper.py").write_text("print('release helper')\n", encoding="utf-8")
    (repo / "src" / "postprocess.py").write_text("print('postprocess')\n", encoding="utf-8")
    (repo / "tools" / "dead_a.sh").write_text("bash dead_b.sh\n", encoding="utf-8")
    (repo / "tools" / "dead_b.sh").write_text("bash dead_a.sh\n", encoding="utf-8")
    first = _commit(repo, "add release boundary")

    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    _commit(repo, "add product file")
    (repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
    third = _commit(repo, "change product file")

    result = scan_repository_metabolism(repo, from_ref=first, to_ref=third, max_commits=3)
    rows = {row["path"]: row for row in result["files"]}

    release = rows["tools/release.sh"]
    assert release["status"] == "active"
    assert release["current_use"]["evidence"]["static_path_references"] == [
        {
            "reference": "tools/release.sh",
            "source": ".github/workflows/release.yml",
        }
    ]

    helper = rows["tools/helper.py"]
    assert helper["status"] == "active"
    assert helper["current_use"]["evidence"]["boundary_path_references"] == [
        {
            "boundary": ".github/workflows/release.yml",
            "reference": "helper.py",
            "source": "tools/release.sh",
        }
    ]

    postprocess = rows["src/postprocess.py"]
    assert postprocess["status"] == "active"
    assert postprocess["current_use"]["evidence"]["boundary_path_references"] == [
        {
            "boundary": ".github/workflows/release.yml",
            "reference": "../src/postprocess.py",
            "source": "tools/release.sh",
        }
    ]

    for path in ("tools/dead_a.sh", "tools/dead_b.sh"):
        assert rows[path]["status"] != "active"
        assert rows[path]["current_use"]["evidence"]["boundary_path_references"] == []
