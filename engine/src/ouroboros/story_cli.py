from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .story import StoryError, compose_story, load_object
from .story_report import write_story_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ouroboros-story", description="Compose existing Ouroboros evidence into one self-contained Anatomy Story.")
    parser.add_argument("scan", help="Current Ouroboros scan JSON")
    parser.add_argument("--history", help="Optional bounded-history JSON")
    parser.add_argument("--drivers", help="Optional Change Drivers JSON")
    parser.add_argument("--context", help="Optional Structural Context JSON")
    parser.add_argument("--json", dest="json_path", help="Write the composed story as JSON")
    parser.add_argument("--report", dest="report_path", nargs="?", const="ouroboros-story.html", metavar="HTML", help="Write the self-contained Anatomy Story report")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _summary(story: dict) -> str:
    current = story["current"]
    lines = [
        f"Ouroboros {__version__} Anatomy Story",
        f"Repository: {story.get('repository')}",
        f"Current commit: {(current.get('sha') or 'unknown')[:10]}",
        f"Product: {current['product_share'] * 100:.1f}% · Machinery: {current['machinery_share'] * 100:.1f}%",
        f"Exact depth: {current['recursive_depth']} · Semantic Index: {current['semantic_index']:.1f}",
        "",
        "Evidence included: " + ", ".join(name.replace("_", " ") for name, enabled in story["sources"].items() if enabled),
    ]
    for warning in story["coherence"]["warnings"]:
        lines.append(f"Note: {warning}")
    lines.append("This composes existing evidence; it adds no new score, policy verdict, or inferred blame.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        story = compose_story(
            load_object(args.scan),
            history=load_object(args.history) if args.history else None,
            drivers=load_object(args.drivers) if args.drivers else None,
            context=load_object(args.context) if args.context else None,
        )
    except (StoryError, OSError, ValueError) as exc:
        print(f"Ouroboros story: {exc}")
        return 2
    if not args.quiet:
        print(_summary(story))
    if args.json_path:
        try:
            target = Path(args.json_path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(story, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros story: could not write JSON: {exc}")
            return 2
    if args.report_path:
        try:
            write_story_report(story, args.report_path)
        except OSError as exc:
            print(f"Ouroboros story: could not write report: {exc}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
