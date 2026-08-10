from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .analyze import analyze_repository
from .classify import classify
from .config import Config, load_config
from .graph import resolve_dependencies
from .report import write_report
from .scanner import scan_repository
from .semantic import build_semantic_graph


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}:1"


def _friendly_summary(path: Path, baseline, semantic) -> str:
    bm = baseline.metrics
    sm = semantic.metrics
    assert sm is not None
    lines = [
        f"Ouroboros {__version__}",
        f"Repository: {path}",
        "",
        "Where did the product go?",
        f"  Product code:        {_percent(bm.direct_product_share)}",
        f"  Product + support:   {_percent(bm.product_plus_essential_share)}",
        f"  Surrounding machinery: {_percent(bm.tooling_share)}",
        f"  Scaffold / product:  {_ratio(bm.scaffolding_ratio)}",
        f"  Audit + meta code:   {_percent(bm.audit_ratio)}",
        f"  File-level depth:    {bm.max_audit_depth}",
        f"  File-level Index:    {bm.ouroboros_index:.1f}/100",
        "",
        "Semantic view",
        f"  Symbols:             {sm.symbol_count:,}",
        f"  Product symbols:     {_percent(sm.direct_product_symbol_share)}",
        f"  Machinery symbols:   {_percent(sm.machinery_symbol_share)}",
        f"  Scaffold / product:  {_ratio(sm.scaffolding_symbol_ratio)}",
        f"  Exact relationships: {_percent(sm.exact_resolution_rate)}",
        f"  Resolvable links:    {_percent(sm.resolution_rate)}",
        f"  Recursive depth:     {sm.max_recursive_depth}",
        f"  Semantic Index:      {sm.semantic_ouroboros_index:.1f}/100",
    ]
    if sm.chain_truncated:
        lines.append("  ⚠ Recursive-chain traversal hit its safety budget; depth may be understated.")
    if baseline.warnings or semantic.diagnostics:
        lines.append("")
        lines.append("Notes")
        lines.extend(f"  - {warning}" for warning in baseline.warnings)
        error_count = sum(d.severity == "error" for d in semantic.diagnostics)
        warning_count = sum(d.severity == "warning" for d in semantic.diagnostics)
        if error_count or warning_count:
            lines.append(f"  - Semantic parser diagnostics: {error_count} error(s), {warning_count} warning(s).")
    lines.extend([
        "",
        "Tip: use --report for a self-contained Repository Anatomy view with exact-chain and classification evidence.",
    ])
    return "\n".join(lines)


def scan(path: str | Path, *, use_repo_config: bool = True) -> tuple[Any, Any]:
    root = Path(path).expanduser().resolve()
    baseline = analyze_repository(root, use_repo_config=use_repo_config)
    config = load_config(root) if use_repo_config else Config()
    scanned = [item for item in scan_repository(root) if not config.ignored(item.component.path)]
    components = [classify(item, override=config.category_for(item.component.path)) for item in scanned]
    file_graph = resolve_dependencies(components)
    semantic = build_semantic_graph(scanned, file_dependencies=file_graph)
    return baseline, semantic


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ouroboros",
        description="See how much of a repository is product versus machinery around the product.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository/folder to scan (default: current folder)")
    parser.add_argument("--json", dest="json_path", help="Also save the full result as JSON")
    parser.add_argument(
        "--report",
        dest="report_path",
        nargs="?",
        const="ouroboros-report.html",
        metavar="HTML",
        help="Write a self-contained Repository Anatomy HTML report (default: ouroboros-report.html)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the friendly text summary")
    parser.add_argument("--canonical", action="store_true", help="Ignore repo-authored .ouroboros.json overrides, like the public Index")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.path).expanduser().resolve()
    try:
        baseline, semantic = scan(root, use_repo_config=not args.canonical)
    except (OSError, ValueError) as exc:
        print(f"Ouroboros could not scan {root}: {exc}")
        return 2

    if not args.quiet:
        print(_friendly_summary(root, baseline, semantic))

    if args.json_path:
        payload = {
            "analyzer": {"name": "Ouroboros", "version": __version__},
            "repository": str(root),
            "baseline": baseline.to_dict(),
            "semantic": semantic.to_dict(),
        }
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
            print(f"\nFull JSON saved to: {target.resolve()}")

    if args.report_path:
        try:
            report_path = write_report(root, baseline, semantic, args.report_path)
        except (OSError, ValueError) as exc:
            print(f"Ouroboros could not write report {args.report_path}: {exc}")
            return 2
        if not args.quiet:
            print(f"\nRepository Anatomy report saved to: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
