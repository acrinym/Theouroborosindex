# Linux proving ground

This benchmark intentionally points Ouroboros at a frozen Linux kernel revision as a large, old, highly modular, C-heavy repository.

## Frozen target

- Repository: `torvalds/linux`
- Branch observed when pinned: `master`
- Commit: `f5bbbfec59b4e2fb7520a91de3df8a6174325d6a`
- Pinned: 2026-08-11

The target SHA is part of the benchmark identity. Do not silently advance it.

## Baseline result — Ouroboros 0.17

The first full canonical run used analyzer head `f3b80080f0c4230c2e276a204b4a683eea561224` on GitHub's `ubuntu-24.04` runner. GitHub terminated the job after the configured two-hour ceiling before semantic analysis completed.

That result is a throughput baseline, not a parser or memory failure:

- setup, pinned Linux checkout, toolchain installation, and environment capture succeeded;
- the full canonical semantic command remained active until the execution ceiling;
- GitHub reported `The job has exceeded the maximum execution time of 2h0m0s`;
- the run did not reach semantic summary, resource-report, or artifact-upload steps;
- no completed semantic JSON exists for the baseline run.

The 0.18 throughput train therefore preserves the same frozen Linux SHA while removing duplicated repository work, eliminating per-symbol full-file line splitting during role refinement, and checkpointing stage progress/timings so a future ceiling is diagnosable instead of opaque.

## Pressure-test contract

The proving-ground run remains deliberately unforgiving: a full canonical semantic scan of the entire checkout using the normal public `ouroboros` command. It does not execute target code and does not pre-slice the kernel into friendly subsystems.

The workflow records:

- exact analyzer and target SHAs;
- runner CPU, memory, and checkout disk footprint;
- GNU `time -v` resource measurements;
- checkpointed repository-scan, baseline-analysis, semantic-parse, role-refinement, and graph-finalization timings;
- semantic parse progress every 500 scanned files;
- canonical semantic JSON when the scan completes;
- a compact summary of file, line, symbol, relationship, resolution, depth, diagnostic, chain-budget, and semantic-index metrics.

The semantic command has its own 105-minute ceiling inside a 120-minute job. If the analyzer still cannot finish, that inner limit leaves time for the `always()` evidence steps to upload the latest timing checkpoint and GNU resource measurements instead of losing the evidence with the job.

A failure is evidence, not a reason to weaken the benchmark. If Linux exposes a scaling, parser, preprocessor, macro, indirection, or truth-boundary problem, fix the product against that observed failure and rerun the same frozen target.

## Planned descent after the full semantic gate

Once the full canonical semantic scan survives with trustworthy output, continue against the same frozen SHA with:

1. Repository Metabolism over a bounded recent first-parent history;
2. Structural Drivers across a defined historical interval;
3. a Value Path chosen from symbols the semantic run actually proves;
4. a Data Journey chosen from data-shaped symbols the semantic run actually proves.

Do not invent selectors or claim exact flow merely to complete the sequence. Linux is the proving ground for Ouroboros's truth boundaries as much as for its throughput.
