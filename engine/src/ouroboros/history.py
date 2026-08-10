from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from . import __version__
from .anatomy import anatomy_fingerprint
from .cli import scan
from .comparison import compare_scans


HARD_MAX_COMMITS = 200
DEFAULT_MAX_COMMITS = 50
MAX_ARCHIVE_FILES = 150_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


class HistoryError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _git(root: Path, *args: str, timeout: float = 30.0) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise HistoryError("git-not-found", "Git is required for bounded history analysis") from exc
    except subprocess.TimeoutExpired as exc:
        raise HistoryError("git-timeout", f"Git command timed out: {' '.join(args)}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown Git error"
        raise HistoryError("git-error", detail)
    return proc.stdout.strip()


def repository_root(path: str | Path) -> Path:
    requested = Path(path).expanduser().resolve()
    if not requested.exists() or not requested.is_dir():
        raise HistoryError("repository-missing", f"Repository path does not exist or is not a directory: {requested}")
    value = _git(requested, "rev-parse", "--show-toplevel")
    root = Path(value).resolve()
    if not root.exists() or not root.is_dir():
        raise HistoryError("repository-missing", f"Git returned an invalid repository root: {root}")
    return root


def resolve_commit(root: Path, ref: str) -> str:
    value = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    sha = value.splitlines()[-1].strip().lower()
    if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        raise HistoryError("invalid-commit", f"Git did not resolve {ref!r} to a full commit SHA")
    return sha


def first_parent_commits(root: Path, from_ref: str, to_ref: str, *, max_commits: int = DEFAULT_MAX_COMMITS) -> list[str]:
    if max_commits < 1 or max_commits > HARD_MAX_COMMITS:
        raise HistoryError("invalid-limit", f"max_commits must be between 1 and {HARD_MAX_COMMITS}")
    start = resolve_commit(root, from_ref)
    end = resolve_commit(root, to_ref)
    rows = [
        line.strip().lower()
        for line in _git(root, "rev-list", "--first-parent", f"--max-count={max_commits + 1}", end).splitlines()
        if line.strip()
    ]
    if start not in rows:
        if len(rows) >= max_commits + 1:
            raise HistoryError(
                "history-range-too-large",
                f"{from_ref!r} was not found within the first {max_commits} first-parent commits ending at {to_ref!r}; "
                f"choose a closer start or raise --max-commits (hard maximum {HARD_MAX_COMMITS})",
            )
        raise HistoryError(
            "not-first-parent",
            f"{from_ref!r} is not on the first-parent history ending at {to_ref!r}",
        )
    index = rows.index(start)
    commits = list(reversed(rows[: index + 1]))
    if len(commits) > max_commits:
        raise HistoryError("history-range-too-large", f"History range contains {len(commits)} commits, above the {max_commits} limit")
    return commits


def commit_metadata(root: Path, sha: str) -> dict[str, str]:
    raw = _git(root, "show", "-s", "--format=%H%x00%aI%x00%s", sha)
    parts = raw.split("\x00", 2)
    if len(parts) != 3:
        raise HistoryError("git-error", f"Could not read commit metadata for {sha}")
    return {"sha": parts[0].lower(), "authored_at": parts[1], "subject": parts[2]}


def _safe_member_path(destination: Path, name: str) -> Path:
    if "\x00" in name or "\\" in name:
        raise HistoryError("unsafe-archive", f"Unsafe archive path: {name!r}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or any(":" in part for part in pure.parts):
        raise HistoryError("unsafe-archive", f"Unsafe archive path: {name!r}")
    target = (destination / Path(*pure.parts)).resolve()
    try:
        target.relative_to(destination.resolve())
    except ValueError as exc:
        raise HistoryError("unsafe-archive", f"Archive path escaped destination: {name!r}") from exc
    return target


def extract_static_archive(archive_path: Path, destination: Path) -> dict[str, int]:
    destination.mkdir(parents=True, exist_ok=True)
    file_count = 0
    byte_count = 0
    skipped_links = 0
    skipped_special = 0
    seen: set[Path] = set()
    try:
        archive = tarfile.open(archive_path, mode="r:")
    except (tarfile.TarError, OSError) as exc:
        raise HistoryError("invalid-archive", "Git archive was not a readable tar file") from exc
    with archive:
        for member in archive:
            target = _safe_member_path(destination, member.name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if member.issym() or member.islnk():
                skipped_links += 1
                continue
            if not member.isfile():
                skipped_special += 1
                continue
            if target in seen:
                raise HistoryError("unsafe-archive", f"Archive contained duplicate path: {member.name!r}")
            seen.add(target)
            file_count += 1
            byte_count += max(0, int(member.size))
            if file_count > MAX_ARCHIVE_FILES:
                raise HistoryError("too-many-files", f"Historical snapshot exceeded {MAX_ARCHIVE_FILES} files")
            if byte_count > MAX_ARCHIVE_BYTES:
                raise HistoryError("snapshot-too-large", f"Historical snapshot exceeded {MAX_ARCHIVE_BYTES} extracted bytes")
            source = archive.extractfile(member)
            if source is None:
                raise HistoryError("invalid-archive", f"Could not read archive member: {member.name!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    return {
        "file_count": file_count,
        "extracted_bytes": byte_count,
        "skipped_links": skipped_links,
        "skipped_special": skipped_special,
    }


def archive_commit(root: Path, sha: str, destination: Path) -> dict[str, int]:
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination.parent / "snapshot.tar"
    try:
        with archive_path.open("wb") as output:
            proc = subprocess.run(
                ["git", "-C", str(root), "archive", "--format=tar", sha],
                check=False,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=60,
            )
    except FileNotFoundError as exc:
        raise HistoryError("git-not-found", "Git is required for bounded history analysis") from exc
    except subprocess.TimeoutExpired as exc:
        raise HistoryError("git-timeout", f"git archive timed out for {sha}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip() or "git archive failed"
        raise HistoryError("git-error", detail)
    return extract_static_archive(archive_path, destination)


def _analyzer_source_sha() -> str | None:
    value = (os.environ.get("OUROBOROS_ANALYZER_SOURCE_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value):
        return value.lower()
    return None


def _scan_payload(repository: Path, sha: str, snapshot: Path) -> tuple[dict[str, Any], dict[str, int]]:
    baseline, semantic = scan(snapshot, use_repo_config=False)
    payload = {
        "schema": {"name": "ouroboros-scan", "version": 2},
        "analyzer": {"name": "Ouroboros", "version": __version__, "source_sha": _analyzer_source_sha()},
        "repository": str(repository),
        "repository_identity": {"git_sha": sha},
        "scan": {
            "canonical": True,
            "target_execution": False,
            "relationship_topology": "exact-only",
            "history_transport": "git-archive",
        },
        "fingerprint": anatomy_fingerprint(baseline, semantic),
        "baseline": baseline.to_dict(),
        "semantic": semantic.to_dict(),
    }
    return payload, {
        "warnings": len(baseline.warnings),
        "semantic_diagnostics": len(semantic.diagnostics),
    }


def _coverage(semantic_metrics: dict[str, Any]) -> float | None:
    if int(semantic_metrics.get("relationship_count") or 0) <= 0:
        return None
    value = semantic_metrics.get("exact_resolution_rate")
    return None if value is None else float(value)


def checkpoint_from_scan(metadata: dict[str, str], payload: dict[str, Any], acquisition: dict[str, int], diagnostics: dict[str, int]) -> dict[str, Any]:
    baseline = payload["baseline"]["metrics"]
    semantic = payload["semantic"]["metrics"]
    profiles = payload["baseline"].get("directory_profiles") or []
    inversion_count = sum(
        1
        for row in profiles
        if isinstance(row, dict)
        and (
            row.get("is_inversion") is True
            or int(row.get("machinery_lines") or 0) > int(row.get("product_lines") or 0) > 0
        )
    )
    return {
        **metadata,
        "product_share": float(baseline.get("direct_product_share") or 0.0),
        "machinery_share": float(baseline.get("tooling_share") or 0.0),
        "scaffolding_ratio": baseline.get("scaffolding_ratio"),
        "recursive_depth": int(semantic.get("max_recursive_depth") or 0),
        "semantic_index": float(semantic.get("semantic_ouroboros_index") or 0.0),
        "exact_coverage": _coverage(semantic),
        "inversion_count": inversion_count,
        "fingerprint": payload.get("fingerprint") or {},
        "acquisition": acquisition,
        "diagnostics": diagnostics,
    }


def _dominance(product: float, machinery: float) -> str:
    if product > machinery:
        return "product"
    if machinery > product:
        return "machinery"
    return "balanced"


def history_events(before: dict[str, Any], after: dict[str, Any], before_meta: dict[str, str], after_meta: dict[str, str]) -> list[dict[str, Any]]:
    comparison = compare_scans(before, after)
    events: list[dict[str, Any]] = []
    product = comparison["metrics"]["product_share"]
    machinery = comparison["metrics"]["machinery_share"]
    left = _dominance(float(product["before"]), float(machinery["before"]))
    right = _dominance(float(product["after"]), float(machinery["after"]))
    if left != right and {left, right} <= {"product", "machinery", "balanced"}:
        events.append(
            {
                "type": "repository-dominance-shift",
                "commit": after_meta["sha"],
                "authored_at": after_meta["authored_at"],
                "subject": after_meta["subject"],
                "before_commit": before_meta["sha"],
                "from": left,
                "to": right,
                "product_share": {"before": product["before"], "after": product["after"]},
                "machinery_share": {"before": machinery["before"], "after": machinery["after"]},
            }
        )
    for crossover in comparison.get("crossovers") or []:
        events.append(
            {
                "type": "directory-crossover",
                "commit": after_meta["sha"],
                "authored_at": after_meta["authored_at"],
                "subject": after_meta["subject"],
                "before_commit": before_meta["sha"],
                "path": crossover["path"],
                "before": crossover["before"],
                "after": crossover["after"],
            }
        )
    depth = comparison["metrics"]["recursive_depth"]
    if depth.get("delta") not in (None, 0, 0.0):
        events.append(
            {
                "type": "recursive-depth-change",
                "commit": after_meta["sha"],
                "authored_at": after_meta["authored_at"],
                "subject": after_meta["subject"],
                "before_commit": before_meta["sha"],
                "before": int(depth["before"]),
                "after": int(depth["after"]),
                "delta": int(depth["after"]) - int(depth["before"]),
            }
        )
    return events


def scan_history(
    path: str | Path,
    *,
    from_ref: str,
    to_ref: str = "HEAD",
    max_commits: int = DEFAULT_MAX_COMMITS,
) -> dict[str, Any]:
    root = repository_root(path)
    commits = first_parent_commits(root, from_ref, to_ref, max_commits=max_commits)
    start_sha = commits[0]
    end_sha = commits[-1]
    checkpoints: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    previous_payload: dict[str, Any] | None = None
    previous_meta: dict[str, str] | None = None

    with tempfile.TemporaryDirectory(prefix="ouroboros-history-") as temp:
        temp_root = Path(temp)
        for index, sha in enumerate(commits):
            commit_dir = temp_root / f"commit-{index:04d}"
            snapshot = commit_dir / "snapshot"
            acquisition = archive_commit(root, sha, snapshot)
            payload, diagnostics = _scan_payload(root, sha, snapshot)
            metadata = commit_metadata(root, sha)
            checkpoints.append(checkpoint_from_scan(metadata, payload, acquisition, diagnostics))
            if previous_payload is not None and previous_meta is not None:
                events.extend(history_events(previous_payload, payload, previous_meta, metadata))
            previous_payload = payload
            previous_meta = metadata
            shutil.rmtree(commit_dir, ignore_errors=True)

    return {
        "schema": {"name": "ouroboros-history", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": __version__, "source_sha": _analyzer_source_sha()},
        "repository": str(root),
        "range": {
            "from_ref": from_ref,
            "from_sha": start_sha,
            "to_ref": to_ref,
            "to_sha": end_sha,
            "commits_scanned": len(commits),
            "max_commits": max_commits,
            "first_parent": True,
            "sampled": False,
        },
        "scan_policy": {
            "canonical": True,
            "target_execution": False,
            "network_access": False,
            "history_transport": "git-archive",
            "every_commit_in_range_scanned": True,
        },
        "checkpoints": checkpoints,
        "events": events,
    }


def write_history_json(result: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return destination.resolve()
