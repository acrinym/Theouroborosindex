# Linux-scale semantic throughput

Ouroboros 0.18 turns the frozen Linux-kernel proving ground into a repeatable performance gate rather than a two-hour black box.

## Observed 0.17 failure

The canonical scan of `torvalds/linux@f5bbbfec59b4e2fb7520a91de3df8a6174325d6a` reached GitHub Actions' configured `2h0m0s` job limit and was cancelled before semantic output was produced. Setup and target checkout had succeeded, and no parser exception or out-of-memory failure was reported.

## Concrete throughput defects found

Static inspection of the canonical path exposed two avoidable scaling costs:

1. `ouroboros.cli.scan()` called `analyze_repository()`, which scanned, decoded, counted, classified, and resolved the entire repository, and then repeated `scan_repository()`, classification, and dependency resolution again before building the semantic graph.
2. `refine_symbol_categories()` called `splitlines()` on the complete source text once for every non-file symbol. A large C translation unit with many declarations therefore repeatedly rebuilt the same line array.

0.18 removes both costs without changing category rules, relationship-resolution rules, or semantic scoring constants.

## Measurement additions

`ouroboros --timings-json PATH` now checkpoints analyzer progress while the normal scan runs. It records:

- repository scan duration and scanned file count;
- file-level baseline analysis duration;
- semantic files total and files parsed;
- semantic symbols and edges accumulated during parsing;
- semantic parse duration;
- symbol-role refinement duration;
- graph-finalization duration;
- semantic and total analysis duration;
- final JSON-write duration when JSON output is requested.

The Linux proving-ground workflow wraps the scan in a 105-minute command timeout inside the 120-minute job timeout. This preserves a tail window for resource reporting and artifact upload if the analyzer still cannot finish. The same frozen Linux SHA remains the target so before/after comparisons stay meaningful.

## Truth contract

These are throughput changes only. They do not make preprocessor-dependent C relationships exact, do not execute target code, and do not relax exact/probable/unresolved relationship semantics. A faster answer must still be the same kind of answer.
