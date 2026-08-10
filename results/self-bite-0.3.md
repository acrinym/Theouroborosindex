# Ouroboros 0.3 — one intentional self-bite 🐍

Ouroboros analyzed **The Ouroboros Index itself exactly once** during PR #1.

- analyzer source head: `382f274bc1782e8a84b95f9124792d388f991d00`
- GitHub Actions run: `31359852498`
- job: `bite-tail-once`
- artifact: `ouroboros-self-bite-once` (`9051947229`)
- result: **passed**
- traversal truncated: **no**
- published recursive chains: **EXACT-only**

## The bite

| Metric | Result |
|---|---:|
| Semantic symbols | 151 |
| Product symbols | 45.0% |
| Machinery symbols | 23.8% |
| Scaffold / product | 0.53:1 |
| Exact relationship rate | 13.4% |
| Resolvable relationship rate | 13.6% |
| Far-from-value symbols | 0.0% |
| Recursive depth | 1 |
| Semantic Ouroboros Index | **3.56** |

## What it taught us

The self-bite exposed a domain-vocabulary collision: functions such as `compute_metrics()` were being labeled **observability** simply because their product job is to compute metrics. In Ouroboros, metrics are the product.

The same qualification run exposed analogous collisions in the frozen public cohort: runtime methods containing words such as `build`, `pipeline`, `receipt`, `verify`, and `bootstrap` could be mistaken for repository machinery even when those words described ordinary application behavior.

0.3 therefore tightened symbol-role refinement after this one bite:

- product/support symbols keep their architectural role; loose machinery vocabulary cannot promote them by itself;
- dedicated machinery paths remain authoritative;
- mixed-purpose files already classified as machinery are refined locally, so genuinely machinery-specific symbols can stay machinery while unrelated symbols fall back to product/support;
- path cues use token boundaries, avoiding substring accidents such as `test` appearing inside `attestation`.

The self-bite job was then removed from recurring CI. The snake bit its tail; it did not consume it.
