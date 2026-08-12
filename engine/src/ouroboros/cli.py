from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, MutableMapping
from pathlib import Path
from time import perf_counter
from typing import Any, Sequence

from . import __version__
from .analyze import analyze_repository, analyze_scanned_repository
from .anatomy import anatomy_fingerprint
from .config import Config, load_config
from .identity import static_git_sha
from .living_report import write_living_report
from .neighbors import MEASUREMENT_MODEL
from .scanner import scan_repository
from .semantic import build_semantic_graph


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}:1"


def _rating(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _friendly_summary(path: Path, baseline, semantic) -> str:
    bm = baseline.metrics
    sm = semantic.metrics
    assert sm is not None
    lines = [
        f"Ouroboros {__version__}",
        f"Repository: {path}",
        "",
        "Where did the product go?",
        f"  Product code:        {_percent(bm.direct_product_share)}",
        f"  Product + support:   {_percent(bm.product_plus_essential_share)}",
        f"  Surrounding machinery: {_percent(bm.tooling_share)}",
        f"  Scaffold / product:  {_ratio(bm.scaffolding_ratio)}",
        f"  Audit + meta code:   {_percent(bm.audit_ratio)}",
        f"  File-level depth:    {bm.max_audit_depth}",
        f"  File-level Index:    {bm.ouroboros_index:.1f}/100",
        "",
        "Semantic view",
        f"  Symbols:             {sm.symbol_count:,}",
        f"  Product symbols:     {_percent(sm.direct_product_symbol_share)}",
        f"  Machinery symbols:   {_percent(sm.machinery_symbol_share)}",
        f"  Scaffold / product:  {_ratio(sm.scaffolding_symbol_ratio)}",
        f"  Exact relationships: {_percent(sm.exact_resolution_rate)}",
        f"  Resolvable links:    {_percent(sm.resolution_rate)}",
        f"  Recursive depth:     {sm.max_recursive_depth}",
        f"  Semantic Index:      {sm.semantic_ouroboros_index:.1f}/100",
    ]
    if sm.chain_truncated:
        lines.append("  ⚠ Recursive-chain traversal hit its safety budget; depth may be understated.")
    if baseline.warnings or semantic.diagnostics:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"  - {warning}" for warning in baseline.warnings)
        error_count = sum(d.severity == "error" for d in semantic.diagnostics)
        warning_count = sum(d.severity == "warning" for d in semantic.diagnostics)
        if error_count or warning_count:
            lines.append(f"  - Semantic parser diagnostics: {error_count} error(s), {warning_count} warning(s).")
    lines.extend([
        "",
        "Tip: use --rating-only for the original scalar Index, or --report for Living Repository Anatomy.",
    ])
    return "\n".join(lines)


def scan(
    path: str | Path,
    *,
    use_repo_config: bool = True,
    timings: MutableMapping[str, Any] | None = None,
    checkpoint: Callable[[], None] | None = None,
) -> tuple[Any, Any]:
    """Run the canonical file and semantic analyses from one shared source scan."""

    total_started = perf_counter()
    root = Path(path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {root}")
    config = load_config(root) if use_repo_config else Config()
    warnings: list[str] = []

    scan_started = perf_counter()
    scanned = [
        item for item in scan_repository(root, warnings=warnings)
        if not config.ignored(item.component.path)
    ]
    if timings is not None:
        timings.update({
            "repository_scan_seconds": perf_counter() - scan_started,
            "scanned_files": len(scanned),
            "stage": "baseline-analysis",
        })
        if checkpoint is not None:
            checkpoint()

    baseline_started = perf_counter()
    baseline = analyze_scanned_repository(root, scanned, config=config, warnings=warnings)
    if timings is not None:
        timings.update({
            "baseline_analysis_seconds": perf_counter() - baseline_started,
            "stage": "semantic-analysis",
        })
        if checkpoint is not None:
            checkpoint()

    # Baseline dependency resolution has already populated each component. Reuse
    # that exact graph rather than resolving the same imports a second time.
    file_graph = {
        component.path: set(component.resolved_dependencies)
        for component in baseline.components
    }
    semantic_started = perf_counter()
    semantic = build_semantic_graph(
        scanned,
        file_dependencies=file_graph,
        telemetry=timings,
        checkpoint=checkpoint,
    )
    if timings is not None:
        timings.update({
            "semantic_analysis_seconds": perf_counter() - semantic_started,
            "total_analysis_seconds": perf_counter() - total_started,
            "stage": "analysis-complete",
        })
        if checkpoint is not None:
            checkpoint()
    return baseline, semantic


def _analyzer_source_sha() -> str | None:
    value = (os.environ.get("OUROBOROS_ANALYZER_SOURCE_SHA") or os.environ.get("GITHUB_SHA") or "").strip()
    if len(value) == 40 and all(char in "0123456789abcdefABCDEF" for char in value):
        return value.lower()
    return None


def _scan_payload(root: Path, baseline, semantic, *, canonical: bool) -> dict:
    return {
        "schema": {"name": "ouroboros-scan", "version": 2},
        "analyzer": {"name": "Ouroboros", "version": __version__, "source_sha": _analyzer_source_sha()},
        "repository": str(root),
        "repository_identity": {"git_sha": static_git_sha(root)},
        "scan": {
            "canonical": canonical,
            "target_execution": False,
            "relationship_topology": "exact-only",
            "measurement_model": MEASUREMENT_MODEL,
        },
        "fingerprint": anatomy_fingerprint(baseline, semantic),
        "baseline": baseline.to_dict(),
        "semantic": semantic.to_dict(),
    }


def _write_timings(path: str | Path, payload: MutableMapping[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(dict(payload), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros",
        description="See how much of a repository is product versus machinery around the product.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository/folder to scan (default: current folder)")
    parser.add_argument("--json", dest="json_path", help="Also save the full result as JSON")
    parser.add_argument(
        "--timings-json",
        dest="timings_path",
        help="Checkpoint scan-stage timings and progress as JSON without changing analysis semantics",
    )
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-report.html",
        metavar="HTML",
        help="Write a self-contained Living Repository Anatomy HTML report (default: ouroboros-report.html)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the friendly text summary")
    parser.add_argument(
        "--rating-only",
        action="store_true",
        help="Print only the original file-level Ouroboros Index as a script-friendly scalar",
    )
    parser.add_argument("--canonical", action="store_true", help="Ignore repo-authored .ouroboros.json overrides, like the public Index")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.rating_only and (args.quiet or args.json_path or args.report_path or args.timings_path):
        parser.error("--rating-only cannot be combined with --quiet, --json, --report, or --timings-json")

    root = Path(args.path).expanduser().resolve()
    if args.rating_only:
        try:
            baseline = analyze_repository(root, use_repo_config=not args.canonical)
        except (OSError, ValueError) as exc:
            print(f"Ouroboros could not scan {root}: {exc}")
            return 2
        print(_rating(baseline.metrics.ouroboros_index))
        return 0

    timings: dict[str, Any] | None = None
    checkpoint: Callable[[], None] | None = None
    if args.timings_path:
        timings = {
            "schema": {"name": "ouroboros-scan-timings", "version": 1},
            "status": "running",
            "repository": str(root),
            "stage": "starting",
        }
        checkpoint = lambda: _write_timings(args.timings_path, timings)  # noqa: E731
        checkpoint()

    try:
        baseline, semantic = scan(
            root,
            use_repo_config=not args.canonical,
            timings=timings,
            checkpoint=checkpoint,
        )
    except (OSError, ValueError) as exc:
        if timings is not None:
            timings.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            assert checkpoint is not None
            checkpoint()
        print(f"Ouroboros could not scan {root}: {exc}")
        return 2

    if not args.quiet:
        print(_friendly_summary(root, baseline, semantic))

    if args.json_path:
        json_started = perf_counter()
        payload = _scan_payload(root, baseline, semantic, canonical=args.canonical)
        target = Path(args.json_path).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            if timings is not None:
                timings.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
                assert checkpoint is not None
                checkpoint()
            print(f"Ouroboros could not write {target}: {exc}")
            return 2
        if timings is not None:
            timings["json_write_seconds"] = perf_counter() - json_started
            assert checkpoint is not None
            checkpoint()
        if not args.quiet:
            print(f"\nFull JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            report_path = write_living_report(root, baseline, semantic, args.report_path)
        except (OSError, ValueError) as exc:
            if timings is not None:
                timings.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
                assert checkpoint is not None
                checkpoint()
            print(f"Ouroboros could not write report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nLiving Repository Anatomy report saved to: {report_path}")

    if timings is not None:
        timings.update({"status": "complete", "stage": "complete"})
        assert checkpoint is not None
        checkpoint()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
