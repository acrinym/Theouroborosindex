# Anatomy Story

Ouroboros 0.11 closes the core exploration loop by composing existing evidence into one report. It does **not** create another analysis system.

Start from a current scan:

```bash
ouroboros /path/to/repo --canonical --json current.json
```

Optionally produce the existing supporting artifacts:

```bash
ouroboros-history /path/to/repo --from <ref> --to HEAD --json history.json
ouroboros-drivers /path/to/repo --before <commit-before> --after <change-commit> --json drivers.json
ouroboros-context corpus.jsonl --scan current.json --json context.json
```

Then compose them:

```bash
ouroboros-story current.json \
  --history history.json \
  --drivers drivers.json \
  --context context.json \
  --json story.json \
  --report
```

The default report is `ouroboros-story.html` and answers four questions in one place:

1. **Where did the product go?** — current product/machinery composition, scaffolding ratio, exact depth, Semantic Index, and exact coverage.
2. **When did the structure move?** — tracked events from Bounded History.
3. **What moved around a selected change?** — file/category/EXACT-chain evidence from Change Drivers.
4. **Is this anatomy unusual?** — neutral corpus position from Structural Context.

Anatomy Story is deterministic presentation. It does not invoke an LLM, rescan repositories, crawl history, generate recommendations, assign developer blame, or manufacture another scalar score.

The composer verifies that each supplied JSON artifact identifies itself with the expected Ouroboros schema (`ouroboros-scan`, `ouroboros-history`, `ouroboros-change-drivers`, or `ouroboros-structural-context`). Structurally similar unrelated JSON is rejected instead of being silently presented as Ouroboros evidence.

If supplied artifacts refer to different known current commit SHAs, the story surfaces coherence notes instead of silently pretending they describe the same state. A Change Drivers artifact may intentionally describe a historical change point rather than the current commit, and is labeled accordingly.

The report is self-contained: no remote JavaScript, CSS, fonts, analytics, or telemetry.

## Why this train exists

Ouroboros already had the evidence, but users otherwise had to open several artifacts and mentally join them. Anatomy Story makes the product loop explicit without adding measurement machinery:

**run → see surprise → locate when → inspect what moved → understand context → act or intentionally do nothing.**
