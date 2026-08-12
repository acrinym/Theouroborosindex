# Ouroboros Product Handoff — After 0.15 Repository Metabolism

Continue active product development in:

- Repository: `acrinym/Theouroborosindex`
- Default branch: `main`
- Public repository: yes
- Bootstrap `main` head before this handoff commit: `85fdd8b20e1434f4ecce66e615769224981f6bc5`
- Open product PRs at handoff: none

## Just shipped

The complete 0.12–0.15 train is merged:

- **0.12 — Rating-First Core + Capability Atlas**: preserves the original Ouroboros number as the front door and adds static capability discovery with bounded EXACT-only implementation neighborhoods.
- **0.13 — Value Paths**: traces deterministic bounded action paths through canonical `EXACT` `CALLS` relationships only.
- **0.14 — Evolution Movie**: scans every accepted first-parent historical commit from inert `git archive` snapshots and plays deterministic Repository Anatomy through time. The Play button bug discovered on the Zork I movie is fixed: stopped-state clicks now call `start()`.
- **0.15 — Repository Metabolism / Dormancy Atlas**: distinguishes absolute machinery/product mass from relative share, records current and last-observed structural-use evidence, and surfaces bounded cleanup-interest classes.

Current package version: `0.15.0`.

## 0.15 operating model

`ouroboros-metabolism` supports recent-count or explicit bounded first-parent history, for example:

```bash
ouroboros-metabolism /repo --since 50
ouroboros-metabolism /repo --from <ref> --to HEAD --json metabolism.json --report
```

For each current file it can report:

- purpose/category and absolute code-line mass;
- supported current-use evidence;
- last observed supported use inside the selected history window;
- first observation and last observed content change inside the window;
- newer conservative version-family siblings;
- one descriptive evidence class: `active`, `dormant`, `superseded-candidate`, `archive-candidate`, `bounded-orphan-candidate`, or `insufficient-evidence`.

The report always keeps **absolute machinery LOC beside machinery share**, because a falling percentage does not prove machinery shrank.

Supported use evidence currently comes from canonical EXACT semantic relationships, resolved local file dependencies, Capability Atlas surfaces/neighborhoods, and separately labeled static workflow/test/manifest path references. The latter are never promoted into canonical topology.

CodeRabbit caught and we fixed an important history-detail bug: `last_observed_change` now fingerprints file content with SHA-256, so same-size/same-LOC edits are still detected.

## Validation receipts

Final pre-merge 0.15 head: `663f224da0b82bba9da024fe4c443133b60586f1`.

GitHub Actions run **#80** / `31549143606` passed on that exact head:

- compile + full engine test suite: **102 tests passed**;
- all CLI version smokes, including `ouroboros-movie` and `ouroboros-metabolism`;
- frozen scans of `permissionlesstech/bitchat`, `srizzon/git-city`, `rdumasia303/deepseek_ocr_app`, and `ryokun6/ryos`;
- aggregate semantic comparison.

CodeRabbit's one actionable 0.15 correctness thread was fixed, replied to, and resolved before merge.

## Product boundaries that remain in force

- The **Ouroboros rating remains the head of the snake**. Deeper surfaces explain the number; they do not replace it.
- Canonical relationship topology remains **EXACT-only**. PROBABLE evidence may be shown but is not canonical truth; UNRESOLVED remains unresolved.
- Target repositories remain inert. Historical transport uses `git archive`; target code is not executed.
- Repository Metabolism supplies evidence, **not safe-delete instructions**. No observed use in a bounded window is not proof of no external, dynamic, manual, or older use.
- High machinery share and high Ouroboros score are not automatically bad.
- Do not build repository-health graders, remediation engines, merge gates, policy/compliance systems, issue generators, audit-of-audit machinery, or review-of-review machinery.

## Natural next descent

The immediate high-value proving ground is `acrinym/zork1`.

Run 0.15 Repository Metabolism across a meaningful recent first-parent window (50–200 commits), inspect what it classifies as dormant / superseded / bounded-orphan / archive candidates, and use the evidence to learn which additional use signals are genuinely needed before extending the model.

The Zork 0.14 movie already demonstrated why 0.15 exists: machinery share fell as product grew, which did **not** establish that machinery itself shrank.

Do not merge future product work unless Justin gives a fresh merge whistle.
