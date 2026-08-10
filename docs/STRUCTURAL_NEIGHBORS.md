# Structural Neighbors

Ouroboros 0.7 makes an Index corpus searchable by repository anatomy.

The question is deliberately structural:

> Which repositories are built from a similar balance of product code, tests, tooling, verification, audit/provenance, process machinery, and recursive machinery even if they solve completely different problems?

Structural Neighbors does **not** rank repository quality. A lower distance only means the two measurements look more alike under the dimensions described below.

## Find neighbors for a repository already in the corpus

```bash
ouroboros-neighbors corpus.jsonl --repo permissionlesstech/bitchat
```

If the corpus contains multiple successful records for that repository, the newest `scanned_at` record is used. Pin an exact record with a full SHA:

```bash
ouroboros-neighbors corpus.jsonl \
  --repo permissionlesstech/bitchat \
  --sha 1f59e814f90c3f489f48d68262cb1bf640bf6181
```

## Compare a local scan to the corpus

First save a normal Ouroboros scan:

```bash
ouroboros /path/to/repo --canonical --json my-repo.json
```

Then use it as the query fingerprint:

```bash
ouroboros-neighbors corpus.jsonl --scan my-repo.json
```

The target repository is not executed by either command.

## Save the neighborhood

```bash
ouroboros-neighbors corpus.jsonl \
  --repo permissionlesstech/bitchat \
  --json neighborhood.json \
  --report
```

`--report` writes `ouroboros-neighborhood.html`, a self-contained local report with no remote scripts, fonts, styles, analytics, or telemetry.

## What distance means

Structural distance is bounded from `0.0` through `1.0`; lower means closer anatomy. It is a weighted combination of independent dimensions:

| Dimension | Weight | Meaning |
|---|---:|---|
| Code-purpose composition | 40% | Distribution of categorized code lines across Ouroboros roles |
| Symbol-role composition | 20% | Distribution of semantic symbols across those roles |
| Recursive depth | 15% | Difference in exact machinery-on-machinery depth, transformed to remain bounded |
| Semantic Index | 10% | Difference in the existing semantic Ouroboros Index |
| Far-from-value share | 10% | Difference in symbols structurally distant from product value |
| Exact relationship coverage | 5% | Difference in exact semantic coverage when both scans have relationships |

If exact relationship coverage is not meaningful for one scan because it observed zero relationships, that dimension is removed rather than treated as either zero or perfect. The remaining weights are renormalized.

The output includes the distance of each dimension and its weighted contribution. This makes the ranking inspectable instead of a black-box similarity score.

## Measurement compatibility

Ouroboros 0.3 introduced the current semantic measurement generation. Releases 0.4 through 0.8 add ingestion, reporting, comparison, neighbor-search, and bounded-history product surfaces without changing that semantic measurement generation, so Structural Neighbors identifies these records as `ouroboros-semantic-v1` for compatibility.

By default, neighbor search requires the same measurement model and the same canonical/non-canonical setting. Incompatible records are excluded from the cohort.

To deliberately include them:

```bash
ouroboros-neighbors corpus.jsonl --repo owner/name --cross-model
```

Cross-model matches are visibly marked as non-comparable. This option is for investigation, not for pretending unlike measurement generations are equivalent.

## Same-repository revisions

By default, other revisions of the query repository are excluded. The feature is meant to surface structural peers rather than tell you that one revision of a repository resembles another revision of itself.

For an evolution-adjacent use case, allow them explicitly:

```bash
ouroboros-neighbors corpus.jsonl --repo owner/name --include-same-repository
```

## Why this belongs in the Index

A corpus becomes much more useful when it can answer questions beyond a single leaderboard or sorted scalar. Structural Neighbors lets the Index expose recurring architectural patterns:

- product-heavy repositories with unusually similar support structure;
- test-dominant repositories whose recursive depth is nevertheless shallow;
- unrelated applications with similar verification/audit topology;
- repositories with similar product/machinery balance but very different semantic depth;
- apparent peers that separate sharply once symbol-role composition is considered.

Those are comparisons to investigate, not verdicts to enforce.
