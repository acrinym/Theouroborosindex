from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .drivers import DEFAULT_DRIVER_LIMIT, scan_change_drivers
from .history import HistoryError
from .drivers_report import write_drivers_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ouroboros-drivers", description="Explain the concrete structural movement between two Git refs.")
    parser.add_argument("path", nargs="?", default=".", help="Local Git repository")
    parser.add_argument("--before", required=True, help="Older commit/ref")
    parser.add_argument("--after", required=True, help="Newer commit/ref")
    parser.add_argument("--limit", type=int, default=DEFAULT_DRIVER_LIMIT, help=f"Maximum file contributors shown (default: {DEFAULT_DRIVER_LIMIT})")
    parser.add_argument("--json", dest="json_path", help="Write machine-readable driver evidence")
    parser.add_argument("--report", dest="report_path", nargs="?", const="ouroboros-drivers.html", metavar="HTML", help="Write a self-contained HTML report")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _summary(result: dict) -> str:
    drivers = result["drivers"]
    lines = [
        f"Ouroboros {__version__} Change Drivers",
        f"Repository: {result['repository']}",
        f"Before: {result['before']['sha'][:10]}  {result['before']['subject']}",
        f"After:  {result['after']['sha'][:10]}  {result['after']['subject']}",
        "",
        "Largest observed file contributors:",
    ]
    for row in drivers.get("files") or []:
        lines.append(f"  {row['path']}  {row['status']}  {row['delta_code_lines']:+,} LOC  {row.get('before_category')} → {row.get('after_category')}")
    if not drivers.get("files"):
        lines.append("  No file-level structural movement was observed.")
    lines.append("")
    lines.append("These are observed structural contributors, not blame or a quality score.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = scan_change_drivers(args.path, before_ref=args.before, after_ref=args.after, limit=args.limit)
    except (HistoryError, OSError, ValueError) as exc:
        print(f"Ouroboros drivers: {exc}")
        return 2
    if not args.quiet:
        print(_summary(result))
    if args.json_path:
        try:
            target = Path(args.json_path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros drivers: could not write JSON: {exc}")
            return 2
    if args.report_path:
        try:
            write_drivers_report(result, args.report_path)
        except OSError as exc:
            print(f"Ouroboros drivers: could not write report: {exc}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
