from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .comparison import compare_scans
from .evolution_report import write_evolution_report


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _load(path: str | Path) -> dict:
    candidate = Path(path).expanduser()
    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{candidate} does not contain a scan object")
    return payload


def _summary(comparison: dict) -> str:
    metrics = comparison["metrics"]
    product = metrics["product_share"]
    machinery = metrics["machinery_share"]
    depth = metrics["recursive_depth"]
    index = metrics["semantic_index"]
    measurement = comparison["measurement"]
    lines = [
        f"Ouroboros Compare {__version__}",
        "",
        "Software evolution",
        f"  Product:          {_pct(product['before'])} → {_pct(product['after'])} ({product['delta'] * 100:+.1f} pp)",
        f"  Machinery:        {_pct(machinery['before'])} → {_pct(machinery['after'])} ({machinery['delta'] * 100:+.1f} pp)",
        f"  Recursive depth:  {int(depth['before'])} → {int(depth['after'])} ({depth['delta']:+.0f})",
        f"  Semantic Index:   {index['before']:.1f} → {index['after']:.1f} ({index['delta']:+.1f})",
    ]
    if not measurement.get("like_for_like_analyzer"):
        lines.extend(["", "Measurement note: analyzer version/source/settings changed; this is not a perfectly like-for-like comparison."])
    if measurement.get("target_sha_changed"):
        lines.append("Target note: the recorded repository SHA changed between scans.")
    explanations = comparison.get("structural_explanations") or []
    if explanations:
        lines.extend(["", "What changed structurally?"])
        lines.extend(f"  - {item}" for item in explanations[:12])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-compare",
        description="Compare two saved Ouroboros scan JSON files without crawling Git history.",
    )
    parser.add_argument("before", help="Earlier Ouroboros scan JSON")
    parser.add_argument("after", help="Later Ouroboros scan JSON")
    parser.add_argument("--json", dest="json_path", help="Save the machine-readable comparison JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-evolution.html",
        metavar="HTML",
        help="Write a self-contained Software Evolution HTML report (default: ouroboros-evolution.html)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the friendly text summary")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        before = _load(args.before)
        after = _load(args.after)
        comparison = compare_scans(before, after)
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        print(f"Ouroboros could not compare the supplied scans: {exc}")
        return 2

    if not args.quiet:
        print(_summary(comparison))

    if args.json_path:
        target = Path(args.json_path).expanduser()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(comparison, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Ouroboros could not write {target}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nComparison JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            report = write_evolution_report(comparison, args.report_path)
        except OSError as exc:
            print(f"Ouroboros could not write evolution report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nSoftware Evolution report saved to: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
