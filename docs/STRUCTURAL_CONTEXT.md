# Structural Context

Ouroboros 0.10 answers **“is this anatomy unusual?”** without turning the Index into a leaderboard.

```bash
ouroboros-context corpus.jsonl --repo owner/name --report
```

A saved local scan can also be contextualized:

```bash
ouroboros /path/to/repo --canonical --json scan.json
ouroboros-context corpus.jsonl --scan scan.json --report
```

The corpus is deduplicated to the newest successful measurement for each repository. Only records with the same declared semantic measurement generation and canonical setting are admitted to the comparable cohort.

Structural Context works entirely from the supplied local JSONL corpus and scan data. It performs no repository acquisition, network lookup, or target-code execution while calculating context.

For each available dimension, the output shows the query value, empirical percentile, comparable sample size, minimum, median, maximum, and a neutral location band. Tail labels require at least 10 comparable measurements for that dimension:

- `insufficient-cohort`: fewer than 10 comparable values; the raw percentile is shown, but no tail claim is made;
- `lower-tail`: below the 10th percentile when the cohort is large enough;
- `middle-range`: 10th through 90th percentile when the cohort is large enough;
- `upper-tail`: above the 90th percentile when the cohort is large enough.

Dimensions include direct product share, machinery share, scaffolding/product ratio, exact recursive depth, Semantic Index, far-from-value symbol share, and exact relationship coverage when that evidence exists.

Percentiles are **relative structural position, not quality rank**. An upper-tail test/tooling share can be appropriate; a lower-tail recursive depth can be appropriate; the Index does not declare either virtuous or defective.

Missing evidence remains `n/a` and is not converted into zero or perfection. Cohort size is shown per dimension so a thin corpus cannot masquerade as strong population knowledge.

The HTML report is self-contained and loads no remote scripts, fonts, analytics, or telemetry.

## Scope boundary

Structural Context adds no scorecard, ranking table, winner/loser language, policy gate, recommendation bot, background crawler, or audit-of-audit mechanism. It contextualizes measurements already present in the Index.
