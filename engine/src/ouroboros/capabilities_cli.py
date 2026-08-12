from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .capabilities import build_capability_atlas
from .capabilities_report import write_capability_report
from .identity import static_git_sha
from .surface_scan import scan_surface_graph as _scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-capabilities",
        description="Map statically evidenced external/user-facing software surfaces to exact implementation neighborhoods.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository/folder to scan (default: current folder)")
    parser.add_argument("--json", dest="json_path", help="Save the Capability Atlas as JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-capabilities.html",
        metavar="HTML",
        help="Write a self-contained HTML Capability Atlas (default: ouroboros-capabilities.html)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the friendly text summary")
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="Ignore repo-authored .ouroboros.json overrides, like the public Index",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser



def _payload(root: Path, atlas, *, canonical: bool) -> dict:
    return {
        "schema": {"name": "ouroboros-capability-atlas", "version": 1},
        "analyzer": {"name": "Ouroboros", "version": __version__},
        "repository": str(root),
        "repository_identity": {"git_sha": static_git_sha(root)},
        "scan": {
            "canonical": canonical,
            "target_execution": False,
            "relationship_topology": "exact-only",
        },
        "atlas": atlas.to_dict(),
    }


def _friendly_summary(root: Path, atlas) -> str:
    lines = [
        f"Ouroboros Capability Atlas {__version__}",
        f"Repository: {root}",
        "",
        f"Discovered surfaces: {len(atlas.capabilities)}",
        f"Semantic anchors:    {atlas.exact_anchored_count}",
        f"Unanchored surfaces: {atlas.unanchored_count}",
    ]
    for capability in atlas.capabilities:
        anchor = "unanchored" if capability.symbol_id is None else (
            f"{len(capability.implementation_files)} file(s), "
            f"{len(capability.implementation_symbols)} symbol(s)"
        )
        lines.append(
            f"  - [{capability.kind}] {capability.name} "
            f"({capability.path}:{capability.line}) -> {anchor}"
        )
    if atlas.warnings:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"  - {warning}" for warning in atlas.warnings)
    lines.extend([
        "",
        "Capability Atlas describes supported static evidence; it does not grade capability quality or recommend architecture.",
    ])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    try:
        scanned, semantic = _scan(root, use_repo_config=not args.canonical)
        atlas = build_capability_atlas(scanned, semantic)
        payload = _payload(root, atlas, canonical=args.canonical)
    except (OSError, ValueError) as exc:
        print(f"Ouroboros could not build a Capability Atlas for {root}: {exc}")
        return 2

    if not args.quiet:
        print(_friendly_summary(root, atlas))

    if args.json_path:
        target = Path(args.json_path).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"Ouroboros could not write {target}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nCapability Atlas JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            report_path = write_capability_report(payload, args.report_path)
        except OSError as exc:
            print(f"Ouroboros could not write report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nCapability Atlas report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
