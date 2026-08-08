# Inaugural semantic benchmark

Ouroboros 0.2 crawls source structure beneath the file/LOC composition baseline. It parses source statically, extracts symbols and relationships, resolves calls/imports/inheritance where possible, and computes Distance From Value and recursive machinery depth from the resulting graph.

Canonical hardened run: `31236501947` at analyzer head `772090ff4f6470732ab7acc244b57dd18942d7e8`.

Canonical topology uses **exactly resolved edges only**. Probable and unresolved relationships remain visible as coverage/evidence but cannot create product reachability, Distance From Value, recursive depth, or the semantic Ouroboros Index. A bare same-name match across programming languages is never promoted to exact; cross-language canonical edges require explicit dependency evidence or a language adapter that can prove the relationship.

## Semantic results

| Repository | Symbols | Product symbols | Machinery symbols | Scaffold/Product | Exact links | Resolvable links | Far >=4 | Depth | Semantic Index |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ryokun6/ryos` | 7,220 | 74.9% | 20.3% | 0.27:1 | 21.5% | 47.3% | 1.1% | 3 | **7.9** |
| `permissionlesstech/bitchat` | 28,365 | 33.7% | 59.4% | 1.77:1 | 36.3% | 66.4% | 3.5% | 2 | **6.0** |
| `srizzon/git-city` | 1,953 | 96.2% | 1.7% | 0.02:1 | 15.2% | 33.4% | 0.1% | 2 | **5.0** |
| `rdumasia303/deepseek_ocr_app` | 37 | 78.4% | 21.6% | 0.28:1 | 3.6% | 9.4% | 0.0% | 0 | **0.0** |

## Baseline versus semantic view

The 0.1 baseline measures code-line composition and file-level topology. The 0.2 semantic view measures symbol composition and exactly resolved source topology. They answer related but different questions, so both remain published.

| Repository | 0.1 product LOC | 0.2 product symbols | 0.1 tooling LOC | 0.2 machinery symbols | 0.1 depth | 0.2 exact depth | 0.1 Index | 0.2 semantic Index |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `ryokun6/ryos` | 75.6% | 74.9% | 22.0% | 20.3% | 2 | 3 | 5.1 | 7.9 |
| `permissionlesstech/bitchat` | 41.0% | 33.7% | 52.7% | 59.4% | 1 | 2 | 2.9 | 6.0 |
| `srizzon/git-city` | 55.4% | 96.2% | 34.6% | 1.7% | 2 | 2 | 5.0 | 5.0 |
| `rdumasia303/deepseek_ocr_app` | 95.4% | 78.4% | 4.6% | 21.6% | 0 | 0 | 0.0 | 0.0 |

## What changed

- `srizzon/git-city` is the clearest demonstration of why the graph exists: 55.4% direct-product LOC in the baseline becomes 96.2% direct-product symbols, with only 1.7% machinery symbols. Repository acreage is not the same thing as architectural machinery.
- `permissionlesstech/bitchat` moves the other direction: 33.7% product symbols versus 59.4% machinery symbols, with a 1.77:1 symbol scaffolding ratio. Its exact graph reaches Distance From Value 12, while canonical recursive machinery depth is 2.
- `ryokun6/ryos` remains strongly product-oriented at 74.9% product symbols and has the cohort's highest semantic Index, 7.9, driven by exact depth 3 plus a small amount of audit/far-from-value structure.
- `rdumasia303/deepseek_ocr_app` remains semantic Index 0.0, but its exact relationship coverage is only 3.6% (9.4% exact+probable). That score is accompanied by an explicit low-coverage signal rather than being presented as a complete reconstruction of runtime structure.

## Hardening discovered during review

The first semantic pass exposed an ambiguous common-name match that could create a false deep Bitchat chain. Canonical topology was changed to exact-only and a regression test was added. OpenHands review then prompted a second edge-case check: a unique same-named symbol in a *different language* could still be promoted to exact. The resolver now treats bare cross-language name matches as probable only. The hardened run removed 21 false-exact Bitchat relationships and 11 far-from-value symbols, moving its precise semantic Index from `6.001939...` to `5.994183...` while leaving the displayed 6.0 rounded score intact.

The scoring weights are named public constants and stay fixed for an analyzer version; they are not per-repository tuning knobs.

## Current interpretation boundary

Version 0.2 has **symbol-level structure** but seeds each symbol's composition category from its containing file's 0.1 classification. Mixed-purpose files are therefore not yet independently classified method-by-method. This is deliberate and visible: the graph foundation is real, while symbol-local role classification remains a separate next refinement.

Dynamic dispatch, reflection, dependency injection, macros, generated code, and other runtime wiring can remain probable or unresolved until a deeper language adapter can prove the edge. Ouroboros does not upgrade uncertainty into a canonical relationship.

Target repository code is never executed by the Index.
