from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .capabilities import build_capability_atlas
from .identity import static_git_sha
from .surface_scan import scan_surface_graph as _scan
from .value_paths import DEFAULT_ALTERNATIVES, DEFAULT_MAX_DEPTH, ValuePathError, select_capability, trace_value_path
from .value_paths_report import write_value_path_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-paths",
        description="Trace one statically supported user action through EXACT call relationships.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository/folder to scan (default: current folder)")
    parser.add_argument("--capability", help="Capability id, exact name, or unique name/id substring to trace")
    parser.add_argument("--list", action="store_true", help="List discovered capability ids and stop")
    parser.add_argument("--json", dest="json_path", help="Save Value Path evidence as JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-value-path.html",
        metavar="HTML",
        help="Write a self-contained HTML Value Path report (default: ouroboros-value-path.html)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=DEFAULT_MAX_DEPTH,
        help=f"Maximum exact call depth to follow (default: {DEFAULT_MAX_DEPTH})",
    )
    parser.add_argument(
        "--alternatives",
        type=int,
        default=DEFAULT_ALTERNATIVES,
        help=f"Number of alternative exact terminal paths to retain (default: {DEFAULT_ALTERNATIVES})",
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
        "schema": {"name": "ouroboros-value-path", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": __version__},
        "repository": str(root),
        "repository_identity": {"git_sha": static_git_sha(root)},
        "scan": {
            "canonical": canonical,
            "target_execution": False,
            "canonical_relationships": "EXACT CALLS only",
        },
        "value_path": analysis.to_dict(),
    }


def _list_text(atlas) -> str:
    lines = ["Capability id\tKind\tName\tAnchor"]
    for capability in atlas.capabilities:
        lines.append(
            f"{capability.id}\t{capability.kind}\t{capability.name}\t{capability.symbol_id or 'unanchored'}"
        )
    if not atlas.capabilities:
        lines.append("<none>\t-\t-\t-")
    return "\n".join(lines)


def _friendly(analysis) -> str:
    strongest = analysis.strongest
    lines = [
        f"Ouroboros Value Paths {__version__}",
        f"Capability: [{analysis.capability.kind}] {analysis.capability.name}",
        f"Anchor: {analysis.capability.symbol_id}",
        "",
        "Strongest exact call path",
    ]
    for index, step in enumerate(strongest.steps):
        prefix = "  " if index == 0 else "  -> "
        lines.append(
            f"{prefix}{step.qualified_name} ({step.path}:{step.line}) [{step.category}]"
        )
    lines.extend([
        "",
        f"Depth: {strongest.depth}",
        f"Files crossed: {strongest.distinct_files}",
        f"Structural categories crossed: {strongest.distinct_categories}",
        f"Alternative exact terminal paths retained: {len(analysis.alternatives)}",
        f"Non-canonical call evidence along path: {strongest.probable_call_boundaries} probable, "
        f"{strongest.unresolved_call_boundaries} unresolved",
    ])
    if analysis.warnings:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"  - {warning}" for warning in analysis.warnings)
    lines.extend([
        "",
        "Strongest means most extensive exact simple call evidence under the documented tie-breaks; it is not a quality or importance score.",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    if args.list and (args.capability or args.json_path or args.report_path or args.quiet):
        parser.error("--list cannot be combined with --capability, --json, --report, or --quiet")

    try:
        scanned, semantic = _scan(root, use_repo_config=not args.canonical)
        atlas = build_capability_atlas(scanned, semantic)
        if args.list:
            if not args.quiet:
                print(_list_text(atlas))
            return 0
        capability = select_capability(atlas, args.capability)
        analysis = trace_value_path(
            capability,
            semantic,
            max_depth=args.max_depth,
            alternatives=args.alternatives,
        )
        payload = _payload(root, analysis, canonical=args.canonical)
    except (OSError, ValueError, ValuePathError) as exc:
        print(f"Ouroboros could not trace a Value Path for {root}: {exc}")
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
            print(f"\nValue Path JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            report_path = write_value_path_report(payload, args.report_path)
        except OSError as exc:
            print(f"Ouroboros could not write report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nValue Path report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
