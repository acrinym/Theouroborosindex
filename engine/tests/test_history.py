from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import ouroboros.history as history_module
import ouroboros.history_cli as history_cli_module
from ouroboros.history import (
    HistoryError,
    archive_commit,
    first_parent_commits,
    history_events,
    repository_root,
    resolve_commit,
)
from ouroboros.history_cli import main as history_main
from ouroboros.history_report import build_history_report_html


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
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


def _payload(
    *,
    product_share: float,
    machinery_share: float,
    depth: int,
    directory_product: int,
    directory_machinery: int,
) -> dict:
    return {
        "analyzer": {"version": "0.8.0", "source_sha": "a" * 40},
        "repository": "/repo",
        "repository_identity": {"git_sha": "b" * 40},
        "scan": {"canonical": True},
        "fingerprint": {"test": True},
        "baseline": {
            "metrics": {
                "direct_product_share": product_share,
                "tooling_share": machinery_share,
                "scaffolding_ratio": machinery_share / product_share if product_share else None,
                "category_code_lines": {"core-product": int(product_share * 100), "testing": int(machinery_share * 100)},
            },
            "directory_profiles": [
                {
                    "path": "src",
                    "product_lines": directory_product,
                    "machinery_lines": directory_machinery,
                    "is_inversion": directory_machinery > directory_product > 0,
                }
            ],
        },
        "semantic": {
            "metrics": {
                "relationship_count": 10,
                "exact_resolution_rate": 0.8,
                "max_recursive_depth": depth,
                "semantic_ouroboros_index": float(depth * 10),
            },
            "chains": [],
        },
    }


def test_first_parent_range_is_inclusive_and_ordered(tmp_path: Path):
    repo = _init_repo(tmp_path / "repo")
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    first = _commit(repo, "first")
    (repo / "app.py").write_text("value = 2\n", encoding="utf-8")
    second = _commit(repo, "second")
    (repo / "app.py").write_text("value = 3\n", encoding="utf-8")
    third = _commit(repo, "third")

    root = repository_root(repo)
    assert first_parent_commits(root, first, third, max_commits=3) == [first, second, third]


def test_option_shaped_ref_is_not_parsed_as_git_option(tmp_path: Path):
    repo = _init_repo(tmp_path / "repo")
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    _commit(repo, "first")

    with pytest.raises(HistoryError):
        resolve_commit(repository_root(repo), "--local-env-vars")


def test_history_range_refuses_sampling_when_bound_is_too_small(tmp_path: Path):
    repo = _init_repo(tmp_path / "repo")
    shas = []
    for index in range(4):
        (repo / "app.py").write_text(f"value = {index}\n", encoding="utf-8")
        shas.append(_commit(repo, f"commit {index}"))

    with pytest.raises(HistoryError) as exc:
        first_parent_commits(repository_root(repo), shas[0], shas[-1], max_commits=3)
    assert exc.value.code == "history-range-too-large"


def test_archive_commit_stops_when_tar_exceeds_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _init_repo(tmp_path / "repo")
    (repo / "app.py").write_text("x" * 32_768, encoding="utf-8")
    sha = _commit(repo, "large snapshot")
    monkeypatch.setattr(history_module, "MAX_ARCHIVE_BYTES", 1024)

    with pytest.raises(HistoryError) as exc:
        archive_commit(repository_root(repo), sha, tmp_path / "snapshot")
    assert exc.value.code == "snapshot-too-large"


def test_history_events_pin_repository_directory_and_depth_changes_to_after_commit():
    before = _payload(
        product_share=0.70,
        machinery_share=0.25,
        depth=1,
        directory_product=70,
        directory_machinery=20,
    )
    after = _payload(
        product_share=0.30,
        machinery_share=0.60,
        depth=3,
        directory_product=30,
        directory_machinery=60,
    )
    before_meta = {"sha": "1" * 40, "authored_at": "2026-08-01T00:00:00Z", "subject": "before"}
    after_meta = {"sha": "2" * 40, "authored_at": "2026-08-02T00:00:00Z", "subject": "after"}

    events = history_events(before, after, before_meta, after_meta)
    assert {event["type"] for event in events} == {
        "repository-dominance-shift",
        "directory-crossover",
        "recursive-depth-change",
    }
    assert all(event["commit"] == "2" * 40 for event in events)
    directory = next(event for event in events if event["type"] == "directory-crossover")
    assert directory["path"] == "src"
    assert directory["before"]["product_lines"] == 70
    assert directory["after"]["machinery_lines"] == 60


def test_history_report_is_self_contained_and_escapes_commit_text():
    result = {
        "repository": "/tmp/<repo>",
        "range": {
            "from_sha": "1" * 40,
            "to_sha": "2" * 40,
            "commits_scanned": 2,
        },
        "checkpoints": [
            {
                "sha": "2" * 40,
                "authored_at": "2026-08-02T00:00:00Z",
                "subject": "<script>alert(1)</script>",
                "product_share": 0.4,
                "machinery_share": 0.5,
                "scaffolding_ratio": 1.25,
                "recursive_depth": 2,
                "semantic_index": 20.0,
                "exact_coverage": 0.8,
            }
        ],
        "events": [],
    }
    text = build_history_report_html(result)
    assert "Ouroboros Bounded History" in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert "<script>alert(1)</script>" not in text
    assert "https://" not in text.lower()
    assert "<script src=" not in text.lower()


def test_history_cli_reports_json_serialization_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    result = {
        "repository": "/repo",
        "range": {"from_sha": "1" * 40, "to_sha": "2" * 40, "commits_scanned": 2},
        "events": [],
    }
    monkeypatch.setattr(history_cli_module, "scan_history", lambda *args, **kwargs: result)

    def fail_json(*args, **kwargs):
        raise ValueError("non-finite metric")

    monkeypatch.setattr(history_cli_module, "write_history_json", fail_json)
    assert history_cli_module.main([".", "--from", "HEAD", "--json", str(tmp_path / "history.json"), "--quiet"]) == 2


def test_history_cli_scans_static_snapshots_without_executing_target_code(tmp_path: Path):
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
        + "\n".join(f"test_padding_{index} = {index}" for index in range(40))
        + "\n",
        encoding="utf-8",
    )
    second = _commit(repo, "add test machinery")

    output = tmp_path / "history.json"
    report = tmp_path / "history.html"
    assert history_main(
        [
            str(repo),
            "--from",
            first,
            "--to",
            second,
            "--max-commits",
            "2",
            "--json",
            str(output),
            "--report",
            str(report),
            "--quiet",
        ]
    ) == 0
    assert not marker.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["range"]["commits_scanned"] == 2
    assert payload["range"]["sampled"] is False
    assert payload["scan_policy"]["canonical"] is True
    assert payload["scan_policy"]["target_execution"] is False
    assert payload["scan_policy"]["network_access"] is False
    assert payload["scan_policy"]["history_transport"] == "git-archive"
    assert report.exists()
