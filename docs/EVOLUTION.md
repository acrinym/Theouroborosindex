# Software Evolution

Ouroboros 0.6 adds the first repository-evolution experience by comparing **two saved Ouroboros scan JSON files**.

It does not crawl Git history, bisect commits, or execute either target repository. That larger history problem is intentionally deferred until two-scan comparison is useful and trustworthy on its own.

## Save two scans

```bash
ouroboros /path/to/repository --canonical --json before.json
# ...the repository changes later...
ouroboros /path/to/repository --canonical --json after.json
```

Compare them:

```bash
ouroboros-compare before.json after.json
```

Write machine-readable comparison data:

```bash
ouroboros-compare before.json after.json --json comparison.json
```

Write the self-contained Software Evolution report:

```bash
ouroboros-compare before.json after.json --report
```

The default report path is `ouroboros-evolution.html`.

## What comparison shows

The comparison keeps current composition and recursive topology as separate axes and reports:

- direct-product share before / after / delta;
- machinery share before / after / delta;
- per-category LOC changes;
- scaffold/product ratio change;
- maximum exact recursive-depth change;
- Semantic Index change;
- exact relationship-coverage change, or `n/a` when a scan contains no semantic relationships;
- scaffolding inversion hotspots added or removed;
- deepest exact chains added, removed, or structurally changed;
- anatomy fingerprints side by side;
- directories that crossed from product-dominant to machinery-dominant.

Structural explanations use descriptive language such as “Testing gained 4,821 LOC” or “Max exact recursive depth increased from 1 to 3.” Ouroboros does not treat those changes as automatically good or bad.

## Scaffolding crossover

For 0.6, a crossover means a directory is present in both supplied scans and:

1. scan A has more direct product LOC than machinery LOC; and
2. scan B has more machinery LOC than direct product LOC.

This is the comparison primitive needed for a future question:

> Which exact commit caused the crossover?

0.6 deliberately does **not** search history for that commit.

## Measurement identity matters

A structural comparison is strongest when both scans use the same analyzer version, analyzer source revision, and canonical-scan setting.

0.6 scan JSON records, where available:

- analyzer version;
- analyzer source SHA supplied by the running environment;
- target repository HEAD SHA discovered by reading Git metadata statically;
- whether canonical mode was used;
- the fact that target execution is disabled and canonical topology is exact-only.

When analyzer versions, source revisions, or canonical settings differ, the comparison explicitly says it is **not perfectly like-for-like**. The structural deltas remain visible, but some difference may come from the measuring instrument rather than the repository.

Older saved scans may lack some identity fields. Missing identity is surfaced as unknown; Ouroboros does not invent provenance.

## Exact means exact

Two-scan comparison preserves the semantic trust model:

- only `EXACT` relationships participate in canonical topology and recursive-depth chains;
- `PROBABLE` remains evidence, not canonical truth;
- zero observed semantic relationships produce `n/a` exact coverage rather than a vacuous 100%.

## What 0.6 does not mean

Comparison is not a code-quality grade, a policy gate, or a recommendation to remove tests/tooling/verification. A larger machinery share can be entirely justified.

The purpose is to answer a narrower question with inspectable evidence:

> **What changed in the shape of this repository?**

Future work may add bounded history traversal and automatic crossover search after this two-scan model has proven useful.
