from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .data_journey import DataJourneyError, data_symbols, select_data_symbol, trace_data_journey
from .data_journey_report import write_data_journey_report
from .identity import static_git_sha
from .surface_scan import scan_surface_graph as _scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-data",
        description="Map where one data type is created, transformed, persisted, and emitted using bounded static evidence.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository/folder to scan (default: current folder)")
    parser.add_argument("--data", help="Data symbol id, exact name/qualified name, or unique substring")
    parser.add_argument("--list", action="store_true", help="List data-shaped symbols and stop")
    parser.add_argument("--json", dest="json_path", help="Save Data Journey evidence as JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-data-journey.html",
        metavar="HTML",
        help="Write a self-contained HTML Data Journey report (default: ouroboros-data-journey.html)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress friendly text output")
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="Ignore repo-authored .ouroboros.json overrides, like the public Index",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _payload(root: Path, analysis, *, canonical: bool) -> dict:
    return {
        "schema": {"name": "ouroboros-data-journey", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": __version__},
        "repository": str(root),
        "repository_identity": {"git_sha": static_git_sha(root)},
        "scan": {
            "canonical": canonical,
            "target_execution": False,
            "event_requirement": "EXACT CALLS only",
            "role_inference": "constructor/type target or lifecycle verb on exact contained member",
        },
        "data_journey": analysis.to_dict(),
    }


def _list_text(graph) -> str:
    lines = ["Symbol id\tKind\tQualified name\tLocation"]
    for symbol in data_symbols(graph):
        lines.append(
            f"{symbol.id}\t{symbol.kind.value}\t{symbol.qualified_name}\t{symbol.path}:{symbol.start_line}"
        )
    if len(lines) == 1:
        lines.append("<none>\t-\t-\t-")
    return "\n".join(lines)


def _friendly(analysis) -> str:
    symbol = analysis.data_symbol
    lines = [
        f"Ouroboros Data Journey {__version__}",
        f"Data: {symbol.qualified_name} [{symbol.kind}]",
        f"Declaration: {symbol.path}:{symbol.line}",
        "",
        "Observed lifecycle events (EXACT calls)",
    ]
    if not analysis.events:
        lines.append("  <none proven>")
    else:
        current_role = None
        for event in analysis.events:
            if event.role != current_role:
                current_role = event.role
                lines.append(f"  {current_role.upper()}")
            lines.append(
                f"    {event.source.qualified_name} ({event.source.path}:{event.source.line}) "
                f"-> {event.target.qualified_name}"
            )
            lines.append(f"      trust: {event.trust}")

    lines.extend([
        "",
        "Stage counts: " + ", ".join(f"{role}={count}" for role, count in analysis.stage_counts.items()),
        f"Lifecycle-shaped member definitions: {len(analysis.boundaries)}",
        f"EXACT calls examined: {analysis.exact_calls_examined}",
    ])
    if analysis.boundaries:
        lines.append("")
        lines.append("Lifecycle-shaped member definitions")
        for boundary in analysis.boundaries:
            lines.append(
                f"  {boundary.role}: {boundary.member.qualified_name} "
                f"({boundary.member.path}:{boundary.member.line})"
            )
    if analysis.warnings:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"  - {warning}" for warning in analysis.warnings)
    lines.extend([
        "",
        "Data Journey groups evidence by lifecycle role; it is not runtime chronology and does not promote probable calls into canonical flow.",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    if args.list and (args.data or args.json_path or args.report_path or args.quiet):
        parser.error("--list cannot be combined with --data, --json, --report, or --quiet")

    try:
        _scanned, semantic = _scan(root, use_repo_config=not args.canonical)
        if args.list:
            print(_list_text(semantic))
            return 0
        selected = select_data_symbol(semantic, args.data)
        analysis = trace_data_journey(selected, semantic)
        payload = _payload(root, analysis, canonical=args.canonical)
    except (OSError, ValueError, DataJourneyError) as exc:
        print(f"Ouroboros could not build a Data Journey for {root}: {exc}")
        return 2

    if not args.quiet:
        print(_friendly(analysis))

    if args.json_path:
        target = Path(args.json_path).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Ouroboros could not write {target}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nData Journey JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            report_path = write_data_journey_report(payload, args.report_path)
        except OSError as exc:
            print(f"Ouroboros could not write report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nData Journey report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
