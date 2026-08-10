# Repository Anatomy

Ouroboros 0.6 turns the 0.5 Repository Anatomy report into **Living Anatomy**: a self-contained spatial view over the same measurements and evidence used by the CLI and JSON output.

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

## Living repository map

The report now begins with a deterministic repository map:

- directories are spatial regions;
- file area is proportional to code-line mass;
- category supplies visual identity;
- thicker file borders represent greater canonical value distance;
- scaffolding-inversion directories are marked;
- files traversed by the deepest exact semantic chains are marked;
- the interaction path is `map → directory → file → symbol → evidence`.

The map does **not** introduce a second classification or topology system. Clicking through it ultimately filters and opens the existing file- and symbol-evidence explorers. For the same scan, the spatial layout is deterministic.

## Anatomy fingerprint

Each scan also exposes a compact multidimensional fingerprint. It preserves separate dimensions for direct product, user surface, essential support, testing, developer tooling, observability, verification, audit/provenance, process machinery, meta-machinery, far-from-value share, recursive depth, and Semantic Index.

The fingerprint is designed for before/after comparison and future structural-peer exploration. It is deliberately **not** collapsed into a ranking badge or a single new score.

## Existing evidence remains first-class

Living Anatomy retains the 0.5 surfaces:

- key product, machinery, scaffold/product, recursive-depth, Index, and exact-coverage measurements;
- a plain-language reading that keeps machinery share and recursive Ouroboros depth separate;
- complete code-line composition by category;
- directory scaffolding inversions;
- deepest canonical semantic chains with symbol locations, categories, value distance, relationship type, and retained exact-edge evidence;
- exact / probable / unresolved relationship coverage and parser diagnostics;
- searchable file evidence with category, confidence, value distance, imports, dependencies, and retained classifier signals;
- searchable symbol-role evidence with category, confidence, role source, source location, and canonical value distance.

Only `EXACT` relationships participate in canonical topology and recursive depth. `PROBABLE` and `UNRESOLVED` remain visible evidence rather than silently becoming canonical truth.

## Trust boundary

The HTML intentionally includes no remote scripts, fonts, style sheets, analytics, or telemetry. Repository-derived strings are escaped before they enter the report.

Ouroboros treats the target repository as inert static input. Generating Living Anatomy does not execute target code, hooks, package managers, build tools, submodules, or dependencies.

## Bounded evidence display

Very large repositories can contain enormous numbers of files and symbols. To keep a single local HTML report usable, the interactive evidence sections prioritize and display a bounded set of high-value records. The full scan remains available through `--json` when every raw record is needed.

The bounded display does not affect metrics, chains, category totals, fingerprints, or the underlying analysis.

For change through time, see [Software Evolution](EVOLUTION.md).
