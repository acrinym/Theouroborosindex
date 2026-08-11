from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import __version__
from .history import DEFAULT_MAX_COMMITS, HARD_MAX_COMMITS, HistoryError, scan_history, write_history_json
from .history_report import write_history_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-history",
        description="Locate structural change points across a bounded first-parent Git history range.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Local Git repository (default: current directory)")
    parser.add_argument("--from", dest="from_ref", required=True, help="Oldest commit/ref to scan, inclusive")
    parser.add_argument("--to", dest="to_ref", default="HEAD", help="Newest commit/ref to scan, inclusive (default: HEAD)")
    parser.add_argument(
        "--max-commits",
        type=int,
        default=DEFAULT_MAX_COMMITS,
        help=f"Maximum commits allowed in the exact first-parent range (default: {DEFAULT_MAX_COMMITS}, hard max: {HARD_MAX_COMMITS})",
    )
    parser.add_argument("--json", dest="json_path", help="Write bounded-history data as JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-history.html",
        metavar="HTML",
        help="Write a self-contained bounded-history HTML report",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the terminal summary")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _short(sha: str | None) -> str:
    return "unknown" if not sha else sha[:10]


def _summary(result: dict) -> str:
    range_info = result["range"]
    events = result.get("events") or []
    crossovers = [event for event in events if event.get("type") in {"repository-dominance-shift", "directory-crossover"}]
    depth_events = [event for event in events if event.get("type") == "recursive-depth-change"]
    lines = [
        f"Ouroboros {__version__} Bounded History",
        f"Repository: {result['repository']}",
        f"Range: {_short(range_info['from_sha'])} → {_short(range_info['to_sha'])}",
        f"First-parent commits scanned: {range_info['commits_scanned']} (every commit; no sampling)",
        "Target execution: no",
        "Canonical measurement: yes",
        "",
        f"Structural crossover events: {len(crossovers)}",
        f"Recursive-depth changes: {len(depth_events)}",
    ]
    for event in events:
        kind = event.get("type")
        sha = _short(event.get("commit"))
        if kind == "repository-dominance-shift":
            lines.append(f"  {sha}  repository balance: {event.get('from')} → {event.get('to')}  {event.get('subject')}")
        elif kind == "directory-crossover":
            lines.append(f"  {sha}  {event.get('path')}: product-dominant → machinery-dominant  {event.get('subject')}")
        elif kind == "recursive-depth-change":
            lines.append(f"  {sha}  exact depth: {event.get('before')} → {event.get('after')}  {event.get('subject')}")
    if not events:
        lines.append("  No tracked structural change points occurred in this range.")
    lines.extend(
        [
            "",
            "Boundary: this command follows first-parent history only and refuses oversized ranges instead of sampling them.",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = scan_history(
            args.path,
            from_ref=args.from_ref,
            to_ref=args.to_ref,
            max_commits=args.max_commits,
        )
    except (HistoryError, OSError, ValueError) as exc:
        code = f" [{exc.code}]" if isinstance(exc, HistoryError) else ""
        print(f"Ouroboros history{code}: {exc}")
        return 2

    if not args.quiet:
        print(_summary(result))

    if args.json_path:
        try:
            target = write_history_json(result, Path(args.json_path))
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros history: could not write JSON: {exc}")
            return 2
        if not args.quiet:
            print(f"\nBounded history JSON saved to: {target}")

    if args.report_path:
        try:
            report = write_history_report(result, Path(args.report_path))
        except OSError as exc:
            print(f"Ouroboros history: could not write report: {exc}")
            return 2
        if not args.quiet:
            print(f"\nBounded history report saved to: {report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
