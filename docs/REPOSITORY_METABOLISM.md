# Repository Metabolism / Dormancy Atlas

Ouroboros 0.15 introduced a bounded answer to a practical repository question: **what is still observably doing something, and what may be trimmable?** Ouroboros 0.16 extends that evidence across explicit build/runtime boundaries that are themselves reached from recognized workflow, test, or manifest surfaces.

This is descriptive structural evidence, not a cleanup bot or repository-health grader.

## Why absolute machinery mass matters

A machinery percentage can fall simply because product code grows faster. Repository Metabolism therefore records both:

- absolute machinery code lines through time;
- machinery share of non-documentation code through time;
- absolute product code lines;
- product share.

A falling percentage is composition evidence. It is never presented as proof that machinery shrank.

## Usage

```bash
ouroboros-metabolism /path/to/repo --since 50
ouroboros-metabolism /path/to/repo --from v1.0.0 --to HEAD
ouroboros-metabolism /path/to/repo --since 100 --json metabolism.json --report
```

Recent-count history is first-parent, exact, and unsampled. Explicit ranges use the same bounded-history safety limits as the existing time surfaces.

## Observed-use evidence

For each historical snapshot, Ouroboros reuses its inert static authorities and records separate evidence channels:

- cross-file canonical `EXACT` semantic relationships;
- resolved local file dependencies;
- explicit Capability Atlas surfaces;
- files inside bounded exact capability neighborhoods;
- literal repository-path references from recognized workflow, test, and manifest surfaces;
- literal repository-path references reached through a workflow/test/manifest-referenced script or structured build/config file.

The last commit where any supported channel observes a current path is retained as that path's **last observed use inside the selected window**.

Static boundary evidence remains separate from canonical semantic topology. A workflow/test/manifest surface can establish the first trusted edge into build/runtime orchestration; Ouroboros can then follow exact literal repository-relative or source-relative references through recognized script/config file types. Disconnected scripts do not become trusted merely because they reference one another, so a dead cycle cannot self-resurrect as active.

This extension was motivated by the live `acrinym/zork1` proving ground. For example, the Creative Natural Play workflow invokes `glulx/creative-natural-play/qualify.sh`, which explicitly drives `stage.py`, `patch-series.json`, verification helpers, and other release machinery. Those downstream files are operationally reached from a real workflow boundary even when they have no ordinary import edge.

## Evidence classes

- **active** — supported structural-use evidence exists at the current commit.
- **dormant** — no current use evidence, but supported use was observed earlier in the bounded window.
- **superseded-candidate** — no current use evidence and a newer version-family sibling is present, such as release/stage/migration machinery.
- **archive-candidate** — historical/archive/release-oriented documentation with no supported current-use evidence.
- **bounded-orphan-candidate** — a machinery file existed across enough selected frames but no supported use was observed in any of them.
- **insufficient-evidence** — the available evidence does not justify a stronger class.

These are investigation classes. **None means safe to delete.** External consumers, manual recovery tools, dynamic loading, unsupported languages, and use older than the selected history window can remain invisible to static evidence.

## Superseded families

Version-bearing machinery names are compared conservatively when their names contain operational markers such as release, stage, migration, schema, version, or upgrade. A lower-numbered sibling is only surfaced as a superseded candidate when it has no supported current-use evidence and a newer sibling in the same family is present.

## Inert-history contract

Every selected historical commit is transported using `git archive` and scanned statically. Target code is never run. The report records this explicitly.

## Product boundary

Repository Metabolism does not add:

- a repository health score;
- a quality verdict;
- deletion or remediation automation;
- a merge gate;
- policy/compliance machinery;
- issue generation;
- audit-of-audit infrastructure.

The Ouroboros rating remains the product's head. Metabolism explains why machinery exists and how observably alive it appears when the user chooses to descend further.
