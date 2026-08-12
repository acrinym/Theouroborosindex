from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .history import HARD_MAX_COMMITS, HistoryError
from .metabolism import scan_repository_metabolism
from .metabolism_report import write_metabolism_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-metabolism",
        description="Show repository machinery mass, observed vitality, dormancy, and bounded cleanup candidates.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Local Git repository (default: current directory)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--since", type=int, help="Scan this many recent first-parent commits (default: 50)")
    group.add_argument("--from", dest="from_ref", help="Oldest commit/ref to scan, inclusive")
    parser.add_argument("--to", dest="to_ref", default="HEAD", help="Newest commit/ref to scan, inclusive")
    parser.add_argument(
        "--max-commits",
        type=int,
        default=HARD_MAX_COMMITS,
        help=f"Maximum commits for explicit --from ranges (hard max: {HARD_MAX_COMMITS})",
    )
    parser.add_argument("--json", dest="json_path", help="Write machine-readable metabolism evidence")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-metabolism.html",
        metavar="HTML",
        help="Write a self-contained Repository Metabolism HTML report",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the terminal summary")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _summary(result: dict) -> str:
    mass = result["mass"]
    before = mass["start"]
    current = mass["current"]
    delta = mass["delta"]
    counts = result.get("status_counts") or {}
    candidate_total = sum(
        int(counts.get(key, 0))
        for key in ("superseded-candidate", "bounded-orphan-candidate", "dormant", "archive-candidate")
    )
    return "\n".join(
        [
            f"Ouroboros {__version__} Repository Metabolism",
            f"Repository: {result['repository']}",
            f"Frames: {result['range']['commits_scanned']} exact first-parent commits (no sampling)",
            "",
            "Machinery mass",
            f"  Absolute: {before['machinery_lines']:,} → {current['machinery_lines']:,} code lines ({delta['machinery_lines']:+,})",
            f"  Relative: {_pct(before['machinery_share'])} → {_pct(current['machinery_share'])} ({delta['machinery_share'] * 100:+.1f} pp)",
            "  Note: share is composition; it can fall while absolute machinery grows.",
            "",
            "Product mass",
            f"  Absolute: {before['product_lines']:,} → {current['product_lines']:,} code lines ({delta['product_lines']:+,})",
            f"  Relative: {_pct(before['product_share'])} → {_pct(current['product_share'])} ({delta['product_share'] * 100:+.1f} pp)",
            "",
            f"Evidence classes: {', '.join(f'{key}={value}' for key, value in sorted(counts.items()))}",
            f"Cleanup-interest candidates: {candidate_total}",
            "Target execution: no",
            "Deletion recommendation: no",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.since is not None and not (1 <= args.since <= HARD_MAX_COMMITS):
        parser.error(f"--since must be between 1 and {HARD_MAX_COMMITS}")

    try:
        result = scan_repository_metabolism(
            args.path,
            since=50 if args.since is None and args.from_ref is None else args.since,
            from_ref=args.from_ref,
            to_ref=args.to_ref,
            max_commits=args.max_commits,
        )
    except (HistoryError, OSError, ValueError) as exc:
        code = f" [{exc.code}]" if isinstance(exc, HistoryError) else ""
        print(f"Ouroboros metabolism{code}: {exc}")
        return 2

    if not args.quiet:
        print(_summary(result))

    if args.json_path:
        target = Path(args.json_path).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros metabolism: could not write JSON: {exc}")
            return 2
        if not args.quiet:
            print(f"\nRepository Metabolism JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            target = write_metabolism_report(result, args.report_path)
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros metabolism: could not write report: {exc}")
            return 2
        if not args.quiet:
            print(f"\nRepository Metabolism report saved to: {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
