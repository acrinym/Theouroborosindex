# The Ouroboros Index

**Where did the product go?** 🐍

Ouroboros looks at a software repository and separates the thing people actually use from the machinery surrounding it: tests, tooling, verification, observability, audit/provenance, build/process code, and machinery around machinery.

The **Ouroboros Index** is the public, reproducible collection of those measurements. Every published record pins the repository commit and analyzer version used for the scan.

> A higher score is not automatically “bad code.” Tests, build systems, integrity checks, and operational tooling can be valuable. Ouroboros exists to make the tradeoff visible and to answer a simpler question: **how much of the repository is the product, and how far has the surrounding machinery grown?**

## Try it on a repository

Requires Python 3.10 or newer.

```bash
git clone https://github.com/acrinym/Theouroborosindex.git
cd Theouroborosindex
python -m pip install ./engine
ouroboros /path/to/your/repository
```

On Windows PowerShell:

```powershell
ouroboros C:\Repos\MyProject
```

### Make the result easy to explore

Ouroboros 0.6 extends Repository Anatomy into a self-contained **Living Anatomy** report:

```bash
ouroboros /path/to/repo --report
```

That writes `ouroboros-report.html`. Open it in a browser to explore a deterministic spatial repository map, anatomy fingerprint, code composition, scaffolding inversions, deepest exact chains, relationship coverage, file classification reasons, and symbol-role evidence without digging through raw JSON.

Choose a report path explicitly with:

```bash
ouroboros /path/to/repo --report out/my-repo.html
```

The map drills through `directory → file → symbol → evidence` using the same classifications and canonical topology as the rest of the analyzer. The report loads no remote scripts, fonts, styles, analytics, or telemetry. See **[Repository Anatomy](docs/REPOSITORY_ANATOMY.md)** for the full surface.

Save the full machine-readable result with:

```bash
ouroboros /path/to/repo --json ouroboros.json
```

Use `--canonical` if you want the same rule as the public Index: ignore any `.ouroboros.json` supplied by the repository being measured.

### Compare two saved scans

Ouroboros 0.6 adds the first software-evolution surface without crawling Git history:

```bash
ouroboros-compare before.json after.json
```

Create both machine-readable comparison data and a self-contained evolution report with:

```bash
ouroboros-compare before.json after.json --json comparison.json --report
```

The default report is `ouroboros-evolution.html`. Comparison shows product/machinery movement, category deltas, scaffold/product change, recursive-depth and Semantic Index change, exact-coverage change, inversion hotspots, deepest exact-chain changes, anatomy fingerprints, and scaffolding crossovers.

Analyzer version/source/settings and target repository SHAs are surfaced so a changed measuring instrument is not silently presented as repository evolution. See **[Software Evolution](docs/EVOLUTION.md)**.

### Locate when the structure changed

Ouroboros 0.8 adds bounded local Git-history analysis:

```bash
ouroboros-history /path/to/repo --from v1.0.0 --to HEAD
```

Write JSON and a self-contained timeline report with:

```bash
ouroboros-history /path/to/repo \
  --from v1.0.0 \
  --to HEAD \
  --json ouroboros-history.json \
  --report
```

History mode scans **every first-parent commit** in the explicit range using canonical static snapshots from `git archive`. It identifies repository balance shifts, directory product→machinery crossovers, and exact recursive-depth changes. The default bound is 50 commits and the hard maximum is 200; an oversized range is refused rather than sampled and presented as exact.

Historical target code, hooks, package managers, builds, and tests are never executed. See **[Bounded History](docs/BOUNDED_HISTORY.md)** for traversal and trust boundaries.

### Find structural neighbors in the Index

Ouroboros 0.7 turns the public corpus into a structural-neighbor search surface:

```bash
ouroboros-neighbors corpus.jsonl --repo permissionlesstech/bitchat
```

Or compare a saved local scan to the corpus:

```bash
ouroboros /path/to/repo --canonical --json my-repo.json
ouroboros-neighbors corpus.jsonl --scan my-repo.json --report
```

The default report is `ouroboros-neighborhood.html`. Neighbor distance compares code-purpose composition, symbol-role composition, exact recursive depth, Semantic Index, far-from-value share, and exact relationship coverage when coverage is meaningful. Every match exposes the per-dimension distance and weighted contribution so the ranking is inspectable.

**Nearest means similar anatomy, not better code.** By default, other revisions of the same repository and incompatible measurement models are excluded. See **[Structural Neighbors](docs/STRUCTURAL_NEIGHBORS.md)** for the distance model and trust rules.

## Build public Index records

Ouroboros 0.4 adds a reusable ingestion command for public GitHub repositories:

```bash
ouroboros-index permissionlesstech/bitchat --output corpus.jsonl
```

A batch can reuse a target manifest, including the existing inaugural benchmark manifest:

```bash
ouroboros-index --manifest benchmarks/inaugural-four.json --output corpus.jsonl
```

The Index ingester:

- resolves the stable GitHub repository ID and an exact 40-character commit SHA;
- downloads GitHub's archive for that exact SHA instead of cloning/executing the target;
- applies finite archive, extracted-byte, file-count, repository-size, and batch limits;
- rejects unsafe archive paths, links, special members, and duplicate extraction targets;
- scans with canonical rules, ignoring target-authored classification overrides;
- writes compact append-oriented JSONL records;
- deduplicates successful records by repository ID + repository SHA + analyzer version + analyzer source revision;
- keeps product/machinery composition and recursive Ouroboros depth/Index as independent measurement axes;
- records bounded failure reasons without treating a failed attempt as a completed identity.

The target repository remains **inert input data** throughout acquisition and analysis. Ouroboros does not run its code, hooks, package managers, build tools, submodules, or dependencies.

See **[Public Index ingestion](docs/INDEX_INGESTION.md)** for the record identity, trust boundary, corpus shape, limits, and manual bounded Actions batch.

## Start here

**[Read the User Guide](docs/USER_GUIDE.md)** for what the analyzer numbers mean, what to look at first, configuration, supported languages, and how to avoid misreading the score.

## What changed in 0.8

0.8 adds a deliberately bounded temporal surface instead of turning Ouroboros into a general history crawler:

- `ouroboros-history` scans an explicit local Git range from `--from` through `--to`;
- traversal is first-parent, inclusive, and unsampled so an identified change point corresponds to an actually scanned commit;
- the default bound is 50 commits and the hard maximum is 200;
- oversized ranges fail instead of silently sampling checkpoints;
- historical source trees are transported with `git archive` into temporary inert snapshots rather than checked out into the target worktree;
- canonical measurement is forced across the whole range so repository-authored overrides cannot change the measuring instrument between commits;
- repository-level product/machinery dominance shifts are pinned to the commit where the observed balance changes;
- existing directory crossover semantics are reused between adjacent commits rather than inventing a second crossover model;
- exact recursive-depth changes are pinned to the later commit in each adjacent pair;
- compact checkpoints retain commit provenance, anatomy fingerprint, composition, depth, Semantic Index, exact coverage, inversions, archive counts, and diagnostics;
- JSON and a self-contained HTML timeline report are available;
- target code, hooks, builds, package managers, tests, and network activity remain outside the history scan path.

0.8 intentionally does **not** add remote crawling, scheduled scans, commit sampling disguised as exactness, a server/database, policy gates, or autonomous drone support. 🤣

## What changed in 0.7

0.7 makes the Index useful as a structural reference library instead of only a collection of individual measurements:

- `ouroboros-neighbors` searches successful Index JSONL records for repositories with similar anatomy;
- a normal saved scan can be used as the query, so a local repository can be compared to an existing corpus without rescanning the corpus;
- structural distance is decomposed across code-purpose composition, symbol-role composition, recursive depth, Semantic Index, far-from-value share, and exact coverage;
- missing exact coverage is excluded and remaining weights are renormalized instead of inventing certainty;
- results expose the largest category differences and the contribution of every distance dimension;
- same-repository revisions are excluded by default so the feature surfaces structural peers rather than obvious self-similarity;
- semantic releases 0.3 through 0.7 are recognized as the same declared measurement generation while incompatible models/settings are excluded unless explicitly requested;
- `--cross-model` permits investigative comparisons but visibly marks them non-comparable;
- neighborhood JSON and self-contained HTML reports preserve provenance and contain no remote runtime dependencies;
- structural distance is explicitly a resemblance metric, never a quality score or policy gate;
- target repositories remain inert; neighbor search consumes already-produced measurements and executes no target code.

## What changed in 0.6

0.6 makes repository anatomy spatial and gives Ouroboros its first useful form of memory without changing the underlying measurement rules:

- Repository Anatomy gains a deterministic directory/file map where file area follows code-line mass;
- inversion regions, deepest exact-chain files, category identity, and canonical value distance are visible in the map;
- map interactions drill into the existing file/symbol evidence rather than creating a second truth system;
- every scan carries a multidimensional anatomy fingerprint instead of a new scalar ranking score;
- `ouroboros-compare` compares two existing scan JSON files without crawling Git history;
- comparison reports product/machinery movement, category deltas, scaffold/product change, recursive depth, Semantic Index, exact coverage, inversion changes, deepest exact-chain changes, and crossovers;
- structural-change explanations remain descriptive rather than moralizing;
- scan identity records analyzer version/source, canonical setting, and statically discoverable target SHA where available;
- analyzer/version/settings mismatches are disclosed instead of pretending a comparison is perfectly like-for-like;
- zero semantic relationships continue to produce `n/a` coverage rather than vacuous certainty;
- target repositories remain inert static input and canonical topology remains EXACT-only.

0.6 intentionally does **not** add automatic Git-history crawling, commit bisection, policy gates, a leaderboard, recurring self-analysis, or the parked Nibbles-style progress snake.

## What changed in 0.5

0.5 makes the existing analysis substantially easier to understand without changing the measurement rules:

- `ouroboros --report` writes a self-contained interactive HTML Repository Anatomy view;
- a plain-language summary explains the result while keeping machinery share and recursive depth as separate axes;
- category composition shows where repository code mass actually went;
- scaffolding inversion hotspots identify directories where machinery has overtaken direct product code;
- deepest canonical chains expose the exact symbols, locations, relationship types, and retained structural evidence behind recursive-depth claims;
- trust and coverage makes exact, probable, unresolved, warning, and parser-error counts visible beside the conclusions;
- file evidence exposes classifier signals, confidence, imports, resolved dependencies, and value distance;
- symbol evidence exposes role source, confidence, source location, and canonical value distance;
- large evidence sets are bounded in the HTML surface while complete raw records remain available through `--json`;
- the report has no remote runtime dependencies or telemetry.

## What changed in 0.4

0.4 turns the frozen benchmark machinery into a reusable public-Index ingestion product without changing the semantic trust model:

- public GitHub targets resolve to stable repository IDs and exact SHAs;
- the existing benchmark manifest format becomes reusable input;
- exact-SHA GitHub archives replace target Git checkout behavior for ingestion;
- acquisition is independently bounded by reported size, compressed bytes, extracted bytes, file count, timeout, and batch count;
- archive extraction fails closed on traversal paths, links, special members, duplicate paths, and multiple roots;
- every public ingestion scan is canonical and ignores target-supplied `.ouroboros.json` overrides;
- compact JSONL corpus records preserve both product-vs-machinery and recursive-Index dimensions;
- unchanged successful identities skip acquisition and compute;
- failed attempts remain retryable and carry explicit reason codes;
- a manual bounded Actions workflow can produce a small corpus artifact without creating a recurring crawler or committing thousands of result files.

## What changed in 0.3

Ouroboros 0.3 keeps the original file/LOC view and adds a stricter symbol-level semantic view:

- mixed-purpose files can classify methods/functions independently instead of branding the whole file as one role;
- a same-named function in another file is no longer enough to manufacture an `EXACT` relationship;
- Python import bindings preserve qualified evidence such as `physics.resolve` and `pathlib.Path.resolve`;
- exact graph traversal is bounded and reports when the safety budget is reached;
- malformed or pathological files are isolated instead of aborting the whole repository scan;
- JSON output avoids non-standard `Infinity` values;
- the package is directly installable—no source reconstruction step is required.

The semantic layer is **static-only**. Target repository code is treated as data and is never executed.

## The inaugural benchmark

The frozen 0.1 cohort remains in [`results/inaugural-four/README.md`](results/inaugural-four/README.md). Semantic methodology is in [`results/inaugural-four/SEMANTIC.md`](results/inaugural-four/SEMANTIC.md) and [`docs/SEMANTIC_GRAPH.md`](docs/SEMANTIC_GRAPH.md).

The historical 0.2 machine-readable semantic result remains at [`results/inaugural-four/semantic-index.json`](results/inaugural-four/semantic-index.json). The current 0.3 result is published separately at [`results/inaugural-four/semantic-index-0.3.json`](results/inaugural-four/semantic-index-0.3.json), preserving both analyzer generations instead of relabeling old data.
