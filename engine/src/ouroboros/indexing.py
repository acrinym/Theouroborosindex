from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_INDEX_SCHEMA = "ouroboros-index-record/v1"
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_MIB = 1024 * 1024


class IndexingError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class IndexPolicy:
    max_repo_kib: int = 256 * 1024
    max_archive_bytes: int = 128 * _MIB
    max_extracted_bytes: int = 512 * _MIB
    max_files: int = 150_000
    http_timeout_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class IndexTarget:
    repository: str
    sha: str | None = None

    def __post_init__(self) -> None:
        if not _REPOSITORY_RE.fullmatch(self.repository):
            raise ValueError(f"Invalid GitHub repository name: {self.repository!r}")
        if self.sha is not None and not _SHA_RE.fullmatch(self.sha):
            raise ValueError(f"SHA must be a full 40-character Git commit id: {self.sha!r}")


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    repository: str
    repository_id: int
    sha: str
    default_branch: str
    size_kib: int
    archive_url: str
    html_url: str

    def identity_key(self, analyzer_version: str, analyzer_source_revision: str) -> str:
        return ":".join(
            (
                str(self.repository_id),
                self.sha.lower(),
                analyzer_version,
                analyzer_source_revision,
            )
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_limited(response: Any, limit: int, *, code: str) -> bytes:
    data = bytearray()
    while True:
        chunk = response.read(min(1024 * 1024, limit - len(data) + 1))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > limit:
            raise IndexingError(code, f"Response exceeded the {limit} byte safety limit")


class GitHubPublicClient:
    api_root = "https://api.github.com"

    def __init__(
        self,
        *,
        token: str | None = None,
        timeout_seconds: float = 60.0,
        opener: Callable[..., Any] = urlopen,
    ):
        self.token = token
        self.timeout_seconds = timeout_seconds
        self._opener = opener

    def _request(self, url: str) -> Request:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "The-Ouroboros-Index",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return Request(url, headers=headers)

    def _json(self, url: str) -> dict[str, Any]:
        try:
            with self._opener(self._request(url), timeout=self.timeout_seconds) as response:
                payload = _read_limited(response, 8 * _MIB, code="github-response-too-large")
        except HTTPError as exc:
            raise IndexingError("github-http-error", f"GitHub returned HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise IndexingError("github-network-error", f"Could not reach GitHub: {exc.reason}") from exc
        try:
            parsed = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IndexingError("github-invalid-response", "GitHub returned an invalid JSON response") from exc
        if not isinstance(parsed, dict):
            raise IndexingError("github-invalid-response", "GitHub response was not a JSON object")
        return parsed

    def resolve(self, target: IndexTarget) -> RepositorySnapshot:
        owner, name = target.repository.split("/", 1)
        repo_url = f"{self.api_root}/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
        metadata = self._json(repo_url)
        if metadata.get("private"):
            raise IndexingError("private-repository", f"{target.repository} is not public")

        repository_id = metadata.get("id")
        default_branch = metadata.get("default_branch")
        size_kib = metadata.get("size", 0)
        html_url = metadata.get("html_url", f"https://github.com/{target.repository}")
        if not isinstance(repository_id, int) or not isinstance(default_branch, str):
            raise IndexingError("github-invalid-response", "GitHub repository metadata is missing identity fields")
        if not isinstance(size_kib, int):
            size_kib = 0

        ref = target.sha or default_branch
        commit_url = f"{repo_url}/commits/{quote(ref, safe='')}"
        commit = self._json(commit_url)
        sha = commit.get("sha")
        if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
            raise IndexingError("github-invalid-response", "GitHub commit response did not contain a full SHA")
        if target.sha is not None and sha.lower() != target.sha.lower():
            raise IndexingError("sha-mismatch", f"GitHub resolved {target.sha} to a different commit")

        archive_url = f"{repo_url}/tarball/{sha}"
        return RepositorySnapshot(
            repository=target.repository,
            repository_id=repository_id,
            sha=sha.lower(),
            default_branch=default_branch,
            size_kib=max(0, size_kib),
            archive_url=archive_url,
            html_url=str(html_url),
        )

    def download_archive(self, snapshot: RepositorySnapshot, destination: Path, *, limit: int) -> int:
        request = self._request(snapshot.archive_url)
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response, destination.open("wb") as handle:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise IndexingError(
                            "archive-too-large",
                            f"Compressed archive exceeded the {limit} byte safety limit",
                        )
                    handle.write(chunk)
                return total
        except HTTPError as exc:
            raise IndexingError(
                "github-http-error",
                f"GitHub returned HTTP {exc.code} while downloading {snapshot.repository}@{snapshot.sha}",
            ) from exc
        except URLError as exc:
            raise IndexingError("github-network-error", f"Could not download repository archive: {exc.reason}") from exc


def _safe_relative_member(name: str, prefix: str | None) -> tuple[str, Path | None]:
    if "\x00" in name or "\\" in name:
        raise IndexingError("unsafe-archive", f"Unsafe archive path: {name!r}")
    pure = PurePosixPath(name)
    if any(":" in part for part in pure.parts):
        raise IndexingError("unsafe-archive", f"Unsafe archive path: {name!r}")
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise IndexingError("unsafe-archive", f"Unsafe archive path: {name!r}")
    root = pure.parts[0]
    if prefix is not None and root != prefix:
        raise IndexingError("unsafe-archive", "Archive contained more than one top-level root")
    if len(pure.parts) == 1:
        return root, None
    relative = Path(*pure.parts[1:])
    if relative == Path("."):
        return root, None
    return root, relative


def extract_github_archive(
    archive_path: Path,
    destination: Path,
    *,
    max_files: int,
    max_extracted_bytes: int,
) -> tuple[int, int]:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    seen: set[Path] = set()

    def checked_target(relative: Path, member_name: str) -> Path:
        target = (destination_root / relative).resolve()
        try:
            target.relative_to(destination_root)
        except ValueError as exc:
            raise IndexingError("unsafe-archive", f"Archive path escaped destination: {member_name!r}") from exc
        return target
    prefix: str | None = None
    file_count = 0
    extracted_bytes = 0

    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise IndexingError("invalid-archive", "Downloaded repository archive is not a readable gzip tarball") from exc

    with archive:
        for member in archive:
            current_prefix, relative = _safe_relative_member(member.name, prefix)
            if prefix is None:
                prefix = current_prefix
            if relative is None:
                if not member.isdir():
                    raise IndexingError("unsafe-archive", "Archive top-level entry was not a directory")
                continue

            if member.isdir():
                target = checked_target(relative, member.name)
                target.mkdir(parents=True, exist_ok=True)
                continue

            if not member.isfile():
                raise IndexingError("unsafe-archive", f"Unsupported archive member type: {member.name!r}")

            file_count += 1
            if file_count > max_files:
                raise IndexingError("too-many-files", f"Repository archive exceeded {max_files} files")
            extracted_bytes += max(0, member.size)
            if extracted_bytes > max_extracted_bytes:
                raise IndexingError(
                    "extracted-too-large",
                    f"Repository archive exceeded {max_extracted_bytes} extracted bytes",
                )

            target = checked_target(relative, member.name)
            if target in seen:
                raise IndexingError("unsafe-archive", f"Archive contained duplicate path: {relative.as_posix()}")
            seen.add(target)
            target.parent.mkdir(parents=True, exist_ok=True)

            source = archive.extractfile(member)
            if source is None:
                raise IndexingError("invalid-archive", f"Could not read archive member: {member.name!r}")
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)

    if prefix is None:
        raise IndexingError("invalid-archive", "Repository archive was empty")
    return file_count, extracted_bytes


class GitHubArchiveAcquirer:
    def __init__(self, client: GitHubPublicClient, policy: IndexPolicy):
        self.client = client
        self.policy = policy

    def acquire(self, snapshot: RepositorySnapshot, destination: Path) -> dict[str, int]:
        if snapshot.size_kib > self.policy.max_repo_kib:
            raise IndexingError(
                "repository-too-large",
                f"GitHub reports {snapshot.size_kib} KiB, above the {self.policy.max_repo_kib} KiB limit",
            )
        destination.mkdir(parents=True, exist_ok=True)
        archive_path = destination.parent / "repository.tar.gz"
        compressed = self.client.download_archive(
            snapshot,
            archive_path,
            limit=self.policy.max_archive_bytes,
        )
        files, extracted = extract_github_archive(
            archive_path,
            destination,
            max_files=self.policy.max_files,
            max_extracted_bytes=self.policy.max_extracted_bytes,
        )
        return {"archive_bytes": compressed, "file_count": files, "extracted_bytes": extracted}


class JsonlCorpus:
    def __init__(self, path: Path):
        self.path = path

    def successful_identity_keys(self) -> set[str]:
        if not self.path.exists():
            return set()
        keys: set[str] = set()
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise IndexingError(
                        "corpus-invalid",
                        f"{self.path} contains invalid JSON on line {line_number}",
                    ) from exc
                if not isinstance(row, dict) or row.get("status") != "ok":
                    continue
                identity = row.get("identity")
                if isinstance(identity, dict) and isinstance(identity.get("key"), str):
                    keys.add(identity["key"])
        return keys

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, sort_keys=True, allow_nan=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")


def _category_symbol_counts(semantic: Any) -> dict[str, int]:
    counts = Counter(symbol.category.value for symbol in semantic.symbols.values())
    return dict(sorted(counts.items()))


def _representative_chains(semantic: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    by_id = semantic.symbols
    rows: list[dict[str, Any]] = []
    chains = sorted(
        semantic.chains,
        key=lambda chain: (-chain.depth, tuple(chain.symbol_ids)),
    )
    for chain in chains[:limit]:
        symbols = []
        for symbol_id in chain.symbol_ids:
            symbol = by_id.get(symbol_id)
            if symbol is None:
                symbols.append({"id": symbol_id})
            else:
                symbols.append(
                    {
                        "id": symbol_id,
                        "path": symbol.path,
                        "name": symbol.qualified_name,
                    }
                )
        rows.append(
            {
                "depth": chain.depth,
                "symbols": symbols,
                "categories": [category.value for category in chain.categories],
                "relationships": [relationship.value for relationship in chain.relationships],
                "canonical_resolution": "exact",
            }
        )
    return rows


def _scaffolding_inversions(baseline: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    profiles = [profile for profile in baseline.directory_profiles if profile.is_inversion]
    profiles.sort(
        key=lambda profile: (
            -(profile.scaffolding_ratio or 0.0),
            -profile.code_lines,
            profile.path,
        )
    )
    return [
        {
            "path": profile.path,
            "code_lines": profile.code_lines,
            "product_lines": profile.product_lines,
            "machinery_lines": profile.machinery_lines,
            "scaffolding_ratio": profile.scaffolding_ratio,
        }
        for profile in profiles[:limit]
    ]


def compact_measurement(baseline: Any, semantic: Any) -> dict[str, Any]:
    if semantic.metrics is None:
        raise IndexingError("analysis-error", "Semantic analysis did not produce metrics")
    baseline_metrics = baseline.metrics.to_dict()
    category_code_lines = baseline_metrics.pop("category_code_lines", {})
    semantic_metrics = semantic.metrics.to_dict()
    diagnostics = Counter(diagnostic.severity for diagnostic in semantic.diagnostics)
    warning_messages = list(baseline.warnings[:25])
    semantic_messages = [
        f"{diagnostic.path}: {diagnostic.message}"
        for diagnostic in semantic.diagnostics[:25]
    ]
    return {
        "baseline": baseline_metrics,
        "semantic": semantic_metrics,
        "category_code_lines": category_code_lines,
        "category_symbol_counts": _category_symbol_counts(semantic),
        "diagnostics": dict(sorted(diagnostics.items())),
        "warnings": warning_messages,
        "semantic_diagnostic_samples": semantic_messages,
        "scaffolding_inversions": _scaffolding_inversions(baseline),
        "representative_deepest_chains": _representative_chains(semantic),
    }


def _identity(snapshot: RepositorySnapshot, analyzer_version: str, analyzer_source_revision: str) -> dict[str, Any]:
    return {
        "key": snapshot.identity_key(analyzer_version, analyzer_source_revision),
        "repository_id": snapshot.repository_id,
        "repository_sha": snapshot.sha,
        "analyzer_version": analyzer_version,
        "analyzer_source_revision": analyzer_source_revision,
    }


def _base_record(
    *,
    snapshot: RepositorySnapshot,
    analyzer_version: str,
    analyzer_source_revision: str,
    status: str,
) -> dict[str, Any]:
    return {
        "schema": _INDEX_SCHEMA,
        "status": status,
        "scanned_at": utc_now(),
        "identity": _identity(snapshot, analyzer_version, analyzer_source_revision),
        "repository": {
            "name": snapshot.repository,
            "id": snapshot.repository_id,
            "sha": snapshot.sha,
            "default_branch": snapshot.default_branch,
            "html_url": snapshot.html_url,
            "reported_size_kib": snapshot.size_kib,
        },
        "analyzer": {
            "name": "Ouroboros",
            "version": analyzer_version,
            "source_revision": analyzer_source_revision,
            "canonical": True,
        },
    }


class IndexRunner:
    def __init__(
        self,
        *,
        client: GitHubPublicClient,
        policy: IndexPolicy,
        analyzer_version: str,
        analyzer_source_revision: str,
        analyze: Callable[[Path], tuple[Any, Any]],
        acquirer: GitHubArchiveAcquirer | None = None,
    ):
        self.client = client
        self.policy = policy
        self.analyzer_version = analyzer_version
        self.analyzer_source_revision = analyzer_source_revision
        self.analyze = analyze
        self.acquirer = acquirer or GitHubArchiveAcquirer(client, policy)

    def run(
        self,
        target: IndexTarget,
        *,
        successful_identity_keys: set[str] | None = None,
        refresh: bool = False,
    ) -> dict[str, Any]:
        try:
            snapshot = self.client.resolve(target)
        except IndexingError as exc:
            return {
                "schema": _INDEX_SCHEMA,
                "status": "failed",
                "scanned_at": utc_now(),
                "identity": None,
                "repository": {"name": target.repository, "requested_sha": target.sha},
                "analyzer": {
                    "name": "Ouroboros",
                    "version": self.analyzer_version,
                    "source_revision": self.analyzer_source_revision,
                    "canonical": True,
                },
                "reason": {"code": exc.code, "message": str(exc)},
            }

        base = _base_record(
            snapshot=snapshot,
            analyzer_version=self.analyzer_version,
            analyzer_source_revision=self.analyzer_source_revision,
            status="ok",
        )
        identity_key = base["identity"]["key"]
        if not refresh and successful_identity_keys and identity_key in successful_identity_keys:
            base["status"] = "skipped"
            base["reason"] = {
                "code": "unchanged-head",
                "message": "This repository/SHA has already been scanned by this analyzer revision",
            }
            return base

        try:
            if snapshot.size_kib > self.policy.max_repo_kib:
                raise IndexingError(
                    "repository-too-large",
                    f"GitHub reports {snapshot.size_kib} KiB, above the {self.policy.max_repo_kib} KiB limit",
                )
            with tempfile.TemporaryDirectory(prefix="ouroboros-index-") as temp:
                temp_root = Path(temp)
                checkout = temp_root / "target"
                acquisition = self.acquirer.acquire(snapshot, checkout)
                baseline, semantic = self.analyze(checkout)
            base["acquisition"] = acquisition
            base["measurement"] = compact_measurement(baseline, semantic)
            return base
        except IndexingError as exc:
            base["status"] = "failed"
            base["reason"] = {"code": exc.code, "message": str(exc)}
            return base
        except (OSError, ValueError, RuntimeError) as exc:
            base["status"] = "failed"
            base["reason"] = {"code": "analysis-error", "message": str(exc)}
            return base


def load_manifest(path: Path) -> list[IndexTarget]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IndexingError("manifest-read-error", f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise IndexingError("manifest-invalid", f"{path} is not valid JSON") from exc

    rows: Any
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("targets"), list):
        rows = payload["targets"]
    else:
        raise IndexingError("manifest-invalid", "Manifest must be a list or an object with a 'targets' list")

    targets: list[IndexTarget] = []
    for index, row in enumerate(rows):
        try:
            if isinstance(row, str):
                targets.append(IndexTarget(row))
            elif isinstance(row, dict):
                repository = row.get("repo", row.get("repository"))
                sha = row.get("sha")
                if not isinstance(repository, str) or (sha is not None and not isinstance(sha, str)):
                    raise ValueError("missing repo/repository or invalid sha")
                targets.append(IndexTarget(repository, sha))
            else:
                raise ValueError("target must be a string or object")
        except ValueError as exc:
            raise IndexingError("manifest-invalid", f"Invalid target at index {index}: {exc}") from exc
    return targets


def apply_sha_overrides(targets: Iterable[IndexTarget], overrides: dict[str, str]) -> list[IndexTarget]:
    normalized = {repository.lower(): sha for repository, sha in overrides.items()}
    result: list[IndexTarget] = []
    for target in targets:
        override = normalized.get(target.repository.lower())
        if override is None:
            result.append(target)
            continue
        if target.sha is not None and target.sha.lower() != override.lower():
            raise IndexingError(
                "sha-conflict",
                f"{target.repository} has SHA {target.sha} in the manifest and {override} on the command line",
            )
        result.append(IndexTarget(target.repository, override))
    return result


def deduplicate_targets(targets: Sequence[IndexTarget]) -> list[IndexTarget]:
    seen: set[tuple[str, str | None]] = set()
    result: list[IndexTarget] = []
    for target in targets:
        key = (target.repository.lower(), target.sha.lower() if target.sha else None)
        if key not in seen:
            seen.add(key)
            result.append(target)
    return result


def detect_analyzer_source_revision(package_file: str, version: str) -> str:
    configured = os.getenv("OUROBOROS_ANALYZER_SHA")
    if configured:
        return configured
    package_path = Path(package_file).resolve()
    candidates = [package_path.parent, *package_path.parents]
    for candidate in candidates[:5]:
        try:
            proc = subprocess.run(
                ["git", "-C", str(candidate), "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            break
        sha = proc.stdout.strip()
        if proc.returncode == 0 and _SHA_RE.fullmatch(sha):
            return sha.lower()
    return f"release:{version}"
