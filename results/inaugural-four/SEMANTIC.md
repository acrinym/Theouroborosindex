# Inaugural semantic benchmark

The semantic benchmark asks a different question from the original file/LOC baseline: **what roles do the actual symbols play, and what exact static relationships connect product behavior to surrounding machinery?**

Ouroboros 0.3 is the current semantic model. The earlier 0.2 results remain documented below as historical output because 0.3 intentionally changed the role and trust model.

## Canonical 0.3 run

- analyzer: `Ouroboros 0.3.0`
- analyzer source: `83571940e8d09a76c9869ec4d5a46d82cb012d4f`
- GitHub Actions run: `31360961575`
- aggregate artifact: `9052391519`
- aggregate digest: `sha256:4949926f98a7b9f20bde2d278e85c632f60dfa7b24ea61fb8b1097d5710f553e`
- traversal truncation: **none of the four repositories**
- target code executed: **never**
- target-authored `.ouroboros.json`: **ignored by canonical mode**

The compact reproducible record is in [`semantic-index-0.3.json`](semantic-index-0.3.json).

### 0.3 results

| Repository | Symbols | Product | Machinery | Scaffold/Product | Audit | Meta | Exact | Resolvable | Far recursive machinery | Depth | Semantic Index |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ryokun6/ryos` | 7,662 | 74.2% | 17.4% | 0.23:1 | 0.30% | 0% | 6.3% | 20.9% | 0.08% | 1 | **2.64** |
| `permissionlesstech/bitchat` | 28,365 | 31.9% | **56.9%** | **1.78:1** | 0% | 0% | 17.2% | 36.4% | 0.66% | 1 | **2.63** |
| `srizzon/git-city` | 2,403 | **94.2%** | 0.8% | 0.01:1 | 0% | 0% | 6.7% | 13.2% | 0% | 1 | **2.50** |
| `rdumasia303/deepseek_ocr_app` | 37 | 78.4% | 21.6% | 0.28:1 | 0% | 0% | 2.2% | 2.2% | 0% | 0 | **0.00** |

### The important result

**Tooling-heavy is not the same thing as Ouroboros-heavy.**

Bitchat is the strongest demonstration. More than half its symbols are surrounding machinery and its machinery/product ratio is `1.78:1`, largely because it has an enormous test surface. Yet it has no audit/meta symbol share, only `0.66%` far recursive machinery, exact recursive depth `1`, and a semantic Index of only `2.63`.

That is deliberate. Tests still count in **machinery share** and **scaffolding ratio**, because they really are repository machinery. Ordinary tests do not automatically count as **far recursive machinery**, because Distance From Value is intended to detect chains such as validator → telemetry → analyzer → dashboard-about-the-analyzer, not punish a repository merely for having a large test suite.

Git City shows the other side: repository acreage and architectural machinery are different things. Its 0.1 LOC baseline looked comparatively tooling-heavy, while 0.3 finds `94.2%` product symbols and only `0.8%` machinery symbols.

## What 0.3 fixed

The 0.2 semantic pass was useful precisely because it found its own weak points. ISOupdater then made the defects concrete.

### False exact relationships

A call such as `Path(path).resolve()` could accidentally bind to an unrelated local function named `resolve` merely because the name was unique. 0.3 preserves qualified Python import evidence (`pathlib.Path.resolve`, `physics.resolve`) and treats a bare cross-file same-name candidate as **probable**, not exact.

File dependency data also no longer grants exactness by itself: the actual import target must match the candidate module.

### Mixed-purpose files

0.2 seeded every symbol role from its containing file. A module containing checksum verification, configuration, history, archive handling, and library housekeeping could therefore turn every method into `verification`.

0.3 uses asymmetric symbol-local refinement. Dedicated machinery paths remain authoritative. Mixed machinery-seeded files keep machinery roles only where local evidence supports them; unrelated symbols fall back to product or essential support. Product/support symbols do not get promoted into machinery merely because their business-domain vocabulary contains words such as `build`, `pipeline`, `receipt`, `verify`, `metrics`, or `bootstrap`.

### Recursive distance

The 0.3 semantic Index's far-distance term counts **recursive machinery categories**—observability, verification, audit/provenance, process machinery, and meta-machinery—rather than ordinary testing or generic developer tooling. Test/tooling volume remains visible in machinery share and scaffolding ratio.

### Safety and reproducibility

- canonical topology uses **EXACT relationships only**;
- probable/unresolved relationships remain visible as coverage evidence;
- recursive traversal has an explicit expansion budget and reports truncation;
- parser/adapter failure is isolated per file;
- JSON output is strict (`null`, never non-standard `Infinity`);
- canonical public scans ignore repository-authored classification overrides;
- target repository code is never executed.

## Historical 0.2 results

These numbers are preserved for provenance, not mixed with 0.3 as if they used the same semantics.

| Repository | 0.2 Product symbols | 0.2 Machinery symbols | 0.2 Depth | 0.2 Semantic Index |
|---|---:|---:|---:|---:|
| `ryokun6/ryos` | 74.9% | 20.3% | 3 | 7.9 |
| `permissionlesstech/bitchat` | 33.7% | 59.4% | 2 | 6.0 |
| `srizzon/git-city` | 96.2% | 1.7% | 2 | 5.0 |
| `rdumasia303/deepseek_ocr_app` | 78.4% | 21.6% | 0 | 0.0 |

0.2 inherited symbol roles from whole-file classification and still allowed several weak relationship/role signals that 0.3 deliberately removed. The version change is therefore meaningful, not cosmetic.

## One self-bite, then stop

Ouroboros 0.3 analyzed The Ouroboros Index itself exactly once during development. That run exposed additional domain-vocabulary collisions and directly informed the final role model. The self-analysis job was then removed from recurring CI.

See [`../self-bite-0.3.md`](../self-bite-0.3.md). The snake bit its tail; it did not consume it. 🐍
