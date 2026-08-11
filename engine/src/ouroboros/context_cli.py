from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .context import ContextError, fingerprint_from_context_record, fingerprint_from_context_scan, structural_context
from .context_report import write_context_report
from .neighbors import NeighborError, load_corpus, load_json, select_query_record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ouroboros-context", description="Place repository anatomy in neutral context against a comparable Index corpus.")
    parser.add_argument("corpus", help="Ouroboros Index JSONL corpus")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="Repository already present in the corpus")
    group.add_argument("--scan", help="Saved Ouroboros scan JSON")
    parser.add_argument("--sha", help="Exact corpus SHA when using --repo")
    parser.add_argument("--json", dest="json_path", help="Write machine-readable structural context")
    parser.add_argument("--report", dest="report_path", nargs="?", const="ouroboros-context.html", metavar="HTML", help="Write a self-contained HTML report")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _summary(result: dict) -> str:
    lines = [
        f"Ouroboros {__version__} Structural Context",
        f"Comparable repositories: {result['cohort']['repositories']}",
        "",
    ]
    for row in result["dimensions"].values():
        if row.get("available"):
            lines.append(f"{row['label']}: {row['value']:.3f} · percentile {row['percentile']:.1f} · {row['band']} (n={row['cohort_size']})")
        else:
            lines.append(f"{row['label']}: n/a ({row.get('reason')})")
    lines.extend(["", "Percentiles describe relative structural position only; they are not a quality rank."])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records = load_corpus(args.corpus)
        if args.repo:
            query_record = select_query_record(records, args.repo, sha=args.sha)
            query = fingerprint_from_context_record(query_record)
        else:
            query = fingerprint_from_context_scan(load_json(args.scan))
        result = structural_context(query, records)
    except (NeighborError, ContextError, OSError, ValueError) as exc:
        print(f"Ouroboros context: {exc}")
        return 2
    if not args.quiet:
        print(_summary(result))
    if args.json_path:
        try:
            target = Path(args.json_path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            print(f"Ouroboros context: could not write JSON: {exc}")
            return 2
    if args.report_path:
        try:
            write_context_report(result, args.report_path)
        except OSError as exc:
            print(f"Ouroboros context: could not write report: {exc}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
