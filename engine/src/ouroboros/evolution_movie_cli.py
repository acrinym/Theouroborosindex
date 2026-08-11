from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .evolution_movie import scan_evolution_movie, write_evolution_movie_json
from .evolution_movie_report import write_evolution_movie_report
from .history import DEFAULT_MAX_COMMITS, HARD_MAX_COMMITS, HistoryError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-movie",
        description="Play deterministic Repository Anatomy through an exact bounded first-parent Git range.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Local Git repository (default: current directory)")
    parser.add_argument("--from", dest="from_ref", required=True, help="Oldest commit/ref to scan, inclusive")
    parser.add_argument("--to", dest="to_ref", default="HEAD", help="Newest commit/ref to scan, inclusive (default: HEAD)")
    parser.add_argument(
        "--max-commits",
        type=int,
        default=DEFAULT_MAX_COMMITS,
        help=f"Maximum commits allowed in the exact range (default: {DEFAULT_MAX_COMMITS}, hard max: {HARD_MAX_COMMITS})",
    )
    parser.add_argument("--json", dest="json_path", help="Write machine-readable Evolution Movie data")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-evolution-movie.html",
        metavar="HTML",
        help="Write the self-contained interactive Evolution Movie HTML",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the terminal summary")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _short(sha: str | None) -> str:
    return "unknown" if not sha else sha[:10]


def _summary(result: dict) -> str:
    range_info = result["range"]
    frames = result.get("frames") or []
    changes = sum(len((frame.get("delta") or {}).get("changes") or []) for frame in frames[1:])
    events = result.get("events") or []
    return "\n".join(
        [
            f"Ouroboros {__version__} Evolution Movie",
            f"Repository: {result['repository']}",
            f"Range: {_short(range_info['from_sha'])} → {_short(range_info['to_sha'])}",
            f"Frames: {len(frames)} (every first-parent commit; no sampling)",
            f"Exact mapped file changes: {changes}",
            f"Bounded-history events: {len(events)}",
            "Target execution: no",
            "Quality judgment: no",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = scan_evolution_movie(
            args.path,
            from_ref=args.from_ref,
            to_ref=args.to_ref,
            max_commits=args.max_commits,
        )
    except (HistoryError, OSError, ValueError) as exc:
        code = f" [{exc.code}]" if isinstance(exc, HistoryError) else ""
        print(f"Ouroboros movie{code}: {exc}")
        return 2

    if not args.quiet:
        print(_summary(result))

    if args.json_path:
        try:
            target = write_evolution_movie_json(result, Path(args.json_path))
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros movie: could not write JSON: {exc}")
            return 2
        if not args.quiet:
            print(f"\nEvolution Movie JSON saved to: {target}")

    if args.report_path:
        try:
            report = write_evolution_movie_report(result, Path(args.report_path))
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros movie: could not write report: {exc}")
            return 2
        if not args.quiet:
            print(f"\nEvolution Movie report saved to: {report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
