# Repository Anatomy

Ouroboros 0.5 adds a human-readable, self-contained HTML view over the same evidence used by the CLI and JSON output.

Generate it with:

```bash
ouroboros /path/to/repository --report
```

That writes `ouroboros-report.html` in the current directory. Choose another path by supplying one:

```bash
ouroboros /path/to/repository --report out/my-repo.html
```

`--canonical` works with reports exactly as it does with terminal and JSON output:

```bash
ouroboros /path/to/repository --canonical --report
```

## What the report shows

Repository Anatomy is deliberately an explanation surface, not a second analyzer. It renders measurements and evidence already produced by Ouroboros:

- key product, machinery, scaffold/product, recursive-depth, Index, and exact-coverage measurements;
- a plain-language reading of the result that keeps machinery share and recursive Ouroboros depth separate;
- the complete code-line composition by category;
- directory scaffolding inversions where machinery has overtaken direct product code;
- the deepest canonical semantic chains, including symbol locations, categories, value distance, relationship type, and retained exact-edge evidence;
- exact / probable / unresolved relationship coverage and parser diagnostics;
- a searchable file evidence explorer showing category, confidence, value distance, imports, dependencies, and retained classifier signals;
- a searchable symbol role explorer showing category, confidence, role source, source location, and canonical value distance.

The HTML intentionally includes no remote scripts, fonts, style sheets, analytics, or telemetry. Open it locally in a browser or archive it alongside a scan receipt.

## Why this exists

The terminal summary is useful for a quick read and JSON is useful for machines, but neither is a comfortable way to answer follow-up questions such as:

- Which directory actually contains the inversion?
- What exact chain caused the reported recursive depth?
- Why did this file land in audit/provenance instead of product?
- Was this symbol inherited from a file seed or refined by local role evidence?
- How much of the graph is exact enough to trust canonically?

Repository Anatomy puts those answers in the normal user path without changing the measurements.

## Bounded evidence display

Very large repositories can contain enormous numbers of files and symbols. To keep a single local HTML report usable, the interactive evidence sections prioritize and display a bounded set of high-value records. The full scan remains available through `--json` when every raw record is needed.

The bounded display does not affect metrics, chains, category totals, or the underlying analysis.
