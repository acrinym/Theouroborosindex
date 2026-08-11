from __future__ import annotations

import json
import subprocess
from pathlib import Path

import ouroboros.evolution_movie_cli as movie_cli_module
from ouroboros.evolution_movie import layout_delta, scan_evolution_movie
from ouroboros.evolution_movie_report import build_evolution_movie_report_html


def _file(path: str, weight: int, category: str, distance: int = 0) -> dict:
    return {
        "kind": "file",
        "path": path,
        "x": 0.0,
        "y": 0.0,
        "width": 10.0,
        "height": 10.0,
        "weight": weight,
        "category": category,
        "value_distance": distance,
        "depth": 1,
    }


def _movie_result(subject: str = "second") -> dict:
    return {
        "schema": {"name": "ouroboros-evolution-movie", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": "0.14.0", "source_sha": None},
        "repository": "/tmp/<repo>",
        "range": {
            "from_ref": "a",
            "from_sha": "1" * 40,
            "to_ref": "b",
            "to_sha": "2" * 40,
            "commits_scanned": 2,
            "max_commits": 50,
            "first_parent": True,
            "sampled": False,
        },
        "movie_policy": {
            "canonical": True,
            "target_execution": False,
            "network_access": False,
            "history_transport": "git-archive",
            "every_commit_in_range_scanned": True,
            "layout": "deterministic anatomy spatial_layout",
            "quality_judgment": False,
        },
        "frames": [
            {
                "frame_index": 0,
                "sha": "1" * 40,
                "authored_at": "2026-08-01T00:00:00Z",
                "subject": "first",
                "product_share": 0.7,
                "machinery_share": 0.2,
                "scaffolding_ratio": 2 / 7,
                "recursive_depth": 1,
                "semantic_index": 10.0,
                "exact_coverage": 0.8,
                "inversion_count": 0,
                "fingerprint": {},
                "acquisition": {},
                "diagnostics": {},
                "map": {"width": 1000.0, "height": 620.0, "file_count": 1, "directory_count": 0, "rectangles": [_file("app.py", 10, "core-product")]},
                "delta": {"baseline_frame": True, "summary": {"appeared": 0, "disappeared": 0, "classification_changed": 0, "grew": 0, "shrunk": 0, "value_distance_changed": 0}, "changes": []},
            },
            {
                "frame_index": 1,
                "sha": "2" * 40,
                "authored_at": "2026-08-02T00:00:00Z",
                "subject": subject,
                "product_share": 0.6,
                "machinery_share": 0.3,
                "scaffolding_ratio": 0.5,
                "recursive_depth": 2,
                "semantic_index": 20.0,
                "exact_coverage": 0.9,
                "inversion_count": 0,
                "fingerprint": {},
                "acquisition": {},
                "diagnostics": {},
                "map": {"width": 1000.0, "height": 620.0, "file_count": 1, "directory_count": 0, "rectangles": [_file("app.py", 15, "core-product")]},
                "delta": {"baseline_frame": False, "summary": {"appeared": 0, "disappeared": 0, "classification_changed": 0, "grew": 1, "shrunk": 0, "value_distance_changed": 0}, "changes": [{"path": "app.py", "appeared": False, "disappeared": False, "classification_changed": False, "grew": True, "shrunk": False, "value_distance_changed": False, "before_weight": 10, "after_weight": 15, "weight_delta": 5, "before_category": "core-product", "after_category": "core-product", "before_value_distance": 0, "after_value_distance": 0}]},
            },
        ],
        "events": [{"type": "recursive-depth-change", "commit": "2" * 40, "subject": subject, "before": 1, "after": 2}],
    }


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


def test_layout_delta_keeps_independent_exact_change_flags():
    before = [
        _file("a.py", 10, "core-product", 1),
        _file("b.py", 5, "testing", 2),
        _file("c.py", 8, "essential-support", 2),
    ]
    after = [
        _file("a.py", 15, "user-surface", 3),
        _file("c.py", 3, "essential-support", 2),
        _file("d.py", 4, "developer-tooling", 1),
    ]
    result = layout_delta(before, after)
    assert result["summary"] == {
        "appeared": 1,
        "disappeared": 1,
        "classification_changed": 1,
        "grew": 1,
        "shrunk": 1,
        "value_distance_changed": 1,
    }
    a = next(row for row in result["changes"] if row["path"] == "a.py")
    assert a["grew"] is True
    assert a["classification_changed"] is True
    assert a["value_distance_changed"] is True
    assert a["weight_delta"] == 5


def test_movie_report_is_self_contained_interactive_and_does_not_embed_raw_commit_html():
    report = build_evolution_movie_report_html(_movie_result("</script><script>alert(1)</script>"))
    assert "Ouroboros Evolution Movie" in report
    assert 'id="range"' in report
    assert 'id="play"' in report
    assert "Evolution frame" in report
    assert 'class="frame"' in report
    assert "application/octet-stream" in report
    assert 'aria-label="Playback speed"' in report
    assert "p.onclick=()=>t?stop():start()" in report
    assert "</script><script>alert(1)</script>" not in report
    assert "<script src=" not in report.lower()
    assert "https://" not in report.lower()


def test_movie_scans_every_commit_from_inert_git_archives_and_builds_spatial_frames(tmp_path: Path):
    repo = _init_repo(tmp_path / "repo")
    marker = tmp_path / "TARGET_WAS_EXECUTED"
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "def product_value():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    first = _commit(repo, "product foundation")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_app.py").write_text(
        "def test_value():\n"
        "    assert 1 == 1\n"
        + "\n".join(f"test_padding_{index} = {index}" for index in range(20))
        + "\n",
        encoding="utf-8",
    )
    second = _commit(repo, "add test surface")

    result = scan_evolution_movie(repo, from_ref=first, to_ref=second, max_commits=2)
    assert not marker.exists()
    assert result["range"]["commits_scanned"] == 2
    assert result["range"]["sampled"] is False
    assert result["movie_policy"]["target_execution"] is False
    assert result["movie_policy"]["history_transport"] == "git-archive"
    assert result["movie_policy"]["layout"] == "deterministic anatomy spatial_layout"
    assert len(result["frames"]) == 2
    assert result["frames"][0]["delta"]["baseline_frame"] is True
    paths = {row["path"] for row in result["frames"][1]["map"]["rectangles"] if row["kind"] == "file"}
    assert "src/app.py" in paths
    assert "tests/test_app.py" in paths
    changed = {row["path"] for row in result["frames"][1]["delta"]["changes"]}
    assert "tests/test_app.py" in changed


def test_movie_cli_writes_json_and_report(tmp_path: Path, monkeypatch):
    result = _movie_result()
    monkeypatch.setattr(movie_cli_module, "scan_evolution_movie", lambda *args, **kwargs: result)
    output = tmp_path / "movie.json"
    report = tmp_path / "movie.html"
    assert movie_cli_module.main([".", "--from", "HEAD", "--json", str(output), "--report", str(report), "--quiet"]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"]["name"] == "ouroboros-evolution-movie"
    assert report.exists()
    assert "Ouroboros Evolution Movie" in report.read_text(encoding="utf-8")
