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

Save the full machine-readable result with:

```bash
ouroboros /path/to/repo --json ouroboros.json
```

Use `--canonical` if you want the same rule as the public Index: ignore any `.ouroboros.json` supplied by the repository being measured.

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
