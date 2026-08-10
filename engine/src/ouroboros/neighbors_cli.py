from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from . import __version__
from .neighbors import (
    NeighborError,
    find_neighbors,
    fingerprint_from_record,
    load_corpus,
    load_json,
    select_query_record,
)
from .neighbors_report import write_neighbors_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros-neighbors",
        description="Find repositories with similar Ouroboros anatomy in an Index JSONL corpus.",
    )
    parser.add_argument("corpus", help="Ouroboros Index JSONL corpus")
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--repo", help="Use the newest successful corpus record for owner/name as the query")
    query.add_argument("--scan", help="Use an Ouroboros scan JSON file as the query")
    parser.add_argument("--sha", help="With --repo, select an exact repository SHA")
    parser.add_argument("--limit", type=int, default=10, help="Maximum neighbors to return (default: 10)")
    parser.add_argument(
        "--cross-model",
        action="store_true",
        help="Allow records from a different measurement model/settings; results are explicitly marked non-comparable",
    )
    parser.add_argument(
        "--include-same-repository",
        action="store_true",
        help="Allow other revisions of the same repository to appear as neighbors",
    )
    parser.add_argument("--json", dest="json_path", help="Write the full neighborhood result as JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-neighborhood.html",
        metavar="HTML",
        help="Write a self-contained Structural Neighborhood HTML report",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the terminal neighborhood summary")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _summary(result: dict) -> str:
    query = result["query"]
    cohort = result["cohort"]
    lines = [
        f"Ouroboros {__version__} Structural Neighborhood",
        f"Query: {query.get('repository_name')} @ {query.get('repository_sha') or 'SHA unavailable'}",
        f"Measurement model: {query.get('measurement_model') or 'unknown'}",
        "",
        "Nearest repository anatomy",
    ]
    neighbors = result.get("neighbors", [])
    if not neighbors:
        lines.append("  No eligible neighbors found under the current comparison rules.")
    for rank, match in enumerate(neighbors, 1):
        fingerprint = match["fingerprint"]
        warning = " [cross-model]" if not match.get("comparable_measurement_model") else ""
        lines.append(
            f"  {rank:>2}. {match['repository_name']}  distance={match['distance']:.3f}{warning}  "
            f"product={fingerprint['direct_product_share']*100:.1f}%  "
            f"machinery={fingerprint['machinery_share']*100:.1f}%  "
            f"depth={fingerprint['recursive_depth']}  index={fingerprint['semantic_index']:.1f}"
        )
    lines.extend(
        [
            "",
            f"Cohort: {cohort['eligible']} eligible of {cohort['records_seen']} successful record(s); returned {cohort['returned']}.",
            "Distance is structural resemblance only. Lower means closer anatomy; it is not a quality score.",
        ]
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sha and not args.repo:
        print("Ouroboros neighbors: --sha can only be used with --repo")
        return 2
    try:
        records = load_corpus(args.corpus)
        if args.scan:
            query_record = load_json(args.scan)
        else:
            query_record = select_query_record(records, args.repo, sha=args.sha)
        query = fingerprint_from_record(query_record)
        result = find_neighbors(
            query,
            records,
            limit=args.limit,
            cross_model=args.cross_model,
            include_same_repository=args.include_same_repository,
        )
    except NeighborError as exc:
        print(f"Ouroboros neighbors: {exc}")
        return 2

    if not args.quiet:
        print(_summary(result))

    if args.json_path:
        destination = Path(args.json_path).expanduser()
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"Ouroboros neighbors: could not write {destination}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nNeighborhood JSON saved to: {destination.resolve()}")

    if args.report_path:
        try:
            report = write_neighbors_report(result, args.report_path)
        except OSError as exc:
            print(f"Ouroboros neighbors: could not write report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nStructural Neighborhood report saved to: {report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
