
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Sequence

from . import __version__
from .cli import scan
from .indexing import (
    GitHubPublicClient,
    IndexPolicy,
    IndexRunner,
    IndexTarget,
    IndexingError,
    JsonlCorpus,
    apply_sha_overrides,
    deduplicate_targets,
    detect_analyzer_source_revision,
    load_manifest,
)


def _mib(value: float) -> int:
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError("size limits must be finite and greater than zero")
    return int(value * 1024 * 1024)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def _parse_sha_override(value: str) -> tuple[str, str]:
    repository, separator, sha = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("--sha must use OWNER/REPO=FULL_SHA")
    try:
        target = IndexTarget(repository, sha)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    assert target.sha is not None
    return target.repository, target.sha


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-index",
        description="Build compact canonical Ouroboros Index records for public GitHub repositories.",
    )
    parser.add_argument("repositories", nargs="*", help="Public GitHub repositories in OWNER/REPO form")
    parser.add_argument("--manifest", action="append", default=[], help="JSON target manifest; may be repeated")
    parser.add_argument(
        "--sha",
        action="append",
        default=[],
        type=_parse_sha_override,
        metavar="OWNER/REPO=SHA",
        help="Pin a repository to an exact full commit SHA",
    )
    parser.add_argument("--output", default="ouroboros-index.jsonl", help="Append-oriented JSONL corpus path")
    parser.add_argument("--refresh", action="store_true", help="Rescan even if the exact identity already succeeded")
    parser.add_argument("--max-targets", type=_positive_int, default=100, help="Maximum repositories in one batch")
    parser.add_argument("--max-repo-mib", type=float, default=256.0, help="GitHub-reported repository size limit")
    parser.add_argument("--max-archive-mib", type=float, default=128.0, help="Compressed archive download limit")
    parser.add_argument("--max-extracted-mib", type=float, default=512.0, help="Extracted repository byte limit")
    parser.add_argument("--max-files", type=_positive_int, default=150000, help="Extracted file-count limit")
    parser.add_argument("--timeout", type=float, default=60.0, help="GitHub request timeout in seconds")
    parser.add_argument("--analyzer-source-sha", help="Analyzer source revision recorded in corpus identity")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-repository progress lines")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _targets_from_args(args: argparse.Namespace) -> list[IndexTarget]:
    targets: list[IndexTarget] = []
    for repository in args.repositories:
        try:
            targets.append(IndexTarget(repository))
        except ValueError as exc:
            raise IndexingError("invalid-target", str(exc)) from exc
    for manifest in args.manifest:
        targets.extend(load_manifest(Path(manifest).expanduser()))

    overrides: dict[str, str] = {}
    override_names: dict[str, str] = {}
    for repository, sha in args.sha:
        key = repository.lower()
        if key in overrides:
            raise IndexingError("sha-conflict", f"{repository} was passed to --sha more than once")
        overrides[key] = sha
        override_names[key] = repository
    targets = apply_sha_overrides(targets, {override_names[key]: sha for key, sha in overrides.items()})

    supplied_repositories = {target.repository.lower() for target in targets}
    orphaned_overrides = sorted(set(overrides) - supplied_repositories)
    if orphaned_overrides:
        targets.extend(IndexTarget(override_names[key], overrides[key]) for key in orphaned_overrides)

    targets = deduplicate_targets(targets)
    if not targets:
        raise IndexingError("no-targets", "Provide at least one OWNER/REPO target or --manifest")
    if len(targets) > args.max_targets:
        raise IndexingError(
            "batch-too-large",
            f"Batch contains {len(targets)} targets; --max-targets is {args.max_targets}",
        )
    return targets


def _friendly(record: dict) -> str:
    repository = record.get("repository", {}).get("name", "unknown")
    sha = record.get("repository", {}).get("sha")
    suffix = f"@{sha[:12]}" if isinstance(sha, str) else ""
    status = record.get("status", "unknown").upper()
    if record.get("status") == "ok":
        semantic = record["measurement"]["semantic"]
        return (
            f"{status:7} {repository}{suffix}  "
            f"product={semantic['direct_product_symbol_share'] * 100:.1f}%  "
            f"machinery={semantic['machinery_symbol_share'] * 100:.1f}%  "
            f"depth={semantic['max_recursive_depth']}  "
            f"index={semantic['semantic_ouroboros_index']:.2f}"
        )
    reason = record.get("reason", {})
    return f"{status:7} {repository}{suffix}  {reason.get('code', 'unknown')}: {reason.get('message', '')}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise IndexingError("invalid-policy", "--timeout must be finite and greater than zero")
        targets = _targets_from_args(args)
        policy = IndexPolicy(
            max_repo_kib=_mib(args.max_repo_mib) // 1024,
            max_archive_bytes=_mib(args.max_archive_mib),
            max_extracted_bytes=_mib(args.max_extracted_mib),
            max_files=args.max_files,
            http_timeout_seconds=args.timeout,
        )
    except (IndexingError, argparse.ArgumentTypeError, ValueError) as exc:
        parser.error(str(exc))

    source_revision = args.analyzer_source_sha or detect_analyzer_source_revision(__file__, __version__)
    client = GitHubPublicClient(timeout_seconds=policy.http_timeout_seconds)
    runner = IndexRunner(
        client=client,
        policy=policy,
        analyzer_version=__version__,
        analyzer_source_revision=source_revision,
        analyze=lambda path: scan(path, use_repo_config=False),
    )
    corpus = JsonlCorpus(Path(args.output).expanduser())
    try:
        successful = corpus.successful_identity_keys()
    except IndexingError as exc:
        parser.error(str(exc))

    failures = 0
    for target in targets:
        record = runner.run(target, successful_identity_keys=successful, refresh=args.refresh)
        if record["status"] in {"ok", "failed"}:
            try:
                corpus.append(record)
            except (OSError, ValueError) as exc:
                parser.error(f"Could not append corpus record: {exc}")
        if record["status"] == "ok":
            successful.add(record["identity"]["key"])
        elif record["status"] == "failed":
            failures += 1
        if not args.quiet:
            print(_friendly(record))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
