# Linux proving ground

This benchmark intentionally points Ouroboros at a frozen Linux kernel revision as a large, old, highly modular, C-heavy repository.

## Frozen target

- Repository: `torvalds/linux`
- Branch observed when pinned: `master`
- Commit: `f5bbbfec59b4e2fb7520a91de3df8a6174325d6a`
- Pinned: 2026-08-11

The target SHA is part of the benchmark identity. Do not silently advance it.

## First pressure test

The first run is deliberately simple and unforgiving: a full canonical semantic scan of the entire checkout using the normal public `ouroboros` command. It does not execute target code and does not pre-slice the kernel into friendly subsystems.

The proving-ground workflow records:

- exact analyzer and target SHAs;
- runner CPU, memory, and checkout disk footprint;
- GNU `time -v` resource measurements;
- canonical semantic JSON when the scan completes;
- a compact summary of file, line, symbol, edge, resolution, depth, diagnostic, and semantic-index metrics.

A failure is evidence, not a reason to weaken the benchmark. If Linux exposes a scaling, parser, preprocessor, macro, indirection, or truth-boundary problem, fix the product against that observed failure and rerun the same frozen target.

## Planned descent after the full semantic gate

Once the full canonical semantic scan survives with trustworthy output, continue against the same frozen SHA with:

1. Repository Metabolism over a bounded recent first-parent history;
2. Structural Drivers across a defined historical interval;
3. a Value Path chosen from symbols the semantic run actually proves;
4. a Data Journey chosen from data-shaped symbols the semantic run actually proves.

Do not invent selectors or claim exact flow merely to complete the sequence. Linux is the proving ground for Ouroboros's truth boundaries as much as for its throughput.
