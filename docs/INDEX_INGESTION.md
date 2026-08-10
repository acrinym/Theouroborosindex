# Public Index ingestion

Ouroboros 0.4 adds the first reusable ingestion path for **The Ouroboros Index**. It turns a public GitHub repository into a compact, reproducible corpus record without executing repository code.

The pipeline is intentionally narrow:

`public repository → exact identity → bounded archive → inert source tree → canonical scan → compact JSONL record`

It is an ingestion product, not a crawler scheduler, repository bureaucracy layer, or second analyzer.

## Quick start

Install the engine as usual:

```bash
python -m pip install ./engine
```

Index the current HEAD of one or more public repositories:

```bash
ouroboros-index permissionlesstech/bitchat srizzon/git-city --output corpus.jsonl
```

Pin an exact commit when reproducibility matters:

```bash
ouroboros-index permissionlesstech/bitchat \
  --sha permissionlesstech/bitchat=1f59e814f90c3f489f48d68262cb1bf640bf6181 \
  --output corpus.jsonl
```

The inaugural benchmark manifest already works as an ingestion manifest:

```bash
ouroboros-index --manifest benchmarks/inaugural-four.json --output corpus.jsonl
```

A manifest may either be a JSON array or an object with a `targets` array. Targets can be strings or objects:

```json
{
  "targets": [
    {"repo": "owner/project", "sha": "0123456789abcdef0123456789abcdef01234567"},
    "other/project"
  ]
}
```

Extra descriptive manifest fields are ignored, so benchmark metadata such as provenance or star snapshots does not become measurement input.

## Exact record identity

A successful record is identified by:

`GitHub repository ID + exact repository SHA + analyzer version + analyzer source revision`

The stable GitHub repository ID matters because a repository name can be renamed. The exact SHA matters because a moving branch name is not a reproducible measurement. Analyzer version and source revision matter because the same repository can legitimately measure differently after analyzer changes.

For an unpinned target, ingestion first asks GitHub for the repository's current default branch and resolves that branch to a full 40-character commit SHA. Acquisition then uses that exact SHA.

By default, a corpus skips an identity that already has a successful record. This happens **before archive acquisition and analysis**, so unchanged HEADs do not consume scan compute. A prior failed record does not suppress a retry. `--refresh` explicitly bypasses successful-record deduplication.

## Analyzer source revision

`ouroboros-index` records the analyzer source revision independently from the target repository SHA.

Resolution order is:

1. `--analyzer-source-sha`, when supplied;
2. `OUROBOROS_ANALYZER_SHA`, when supplied by an embedding environment;
3. the installed Ouroboros checkout's own Git HEAD, when available;
4. `release:<version>` for an installed package without Git metadata.

The Git lookup is only for Ouroboros's own installed source. It never invokes Git inside the target repository.

## Target code remains inert

Canonical public ingestion treats every target repository as untrusted input.

Ouroboros does **not**:

- run target scripts or executables;
- invoke target package managers;
- install target dependencies;
- invoke build systems;
- run Git hooks;
- initialize submodules;
- invoke Git LFS or repository-defined filters;
- honor target-authored `.ouroboros.json` classification overrides.

Instead of cloning a target, ingestion downloads GitHub's archive for the exact commit. The archive is opened as data and extracted by a fail-closed extractor before the existing static analyzer sees it.

Archive extraction rejects:

- absolute or parent-traversal paths;
- ambiguous backslash or drive-like path components;
- multiple top-level roots;
- symbolic links and hard links;
- device/special archive members;
- duplicate extracted paths;
- archives that exceed configured file or byte limits.

This keeps the target acquisition boundary smaller than a general-purpose Git checkout.

## Bounded acquisition

Defaults are deliberately finite:

| Bound | Default |
|---|---:|
| Targets per CLI batch | 100 |
| GitHub-reported repository size | 256 MiB |
| Compressed archive download | 128 MiB |
| Extracted repository contents | 512 MiB |
| Extracted files | 150,000 |
| GitHub request timeout | 60 seconds |

Override them explicitly with `--max-targets`, `--max-repo-mib`, `--max-archive-mib`, `--max-extracted-mib`, `--max-files`, and `--timeout`.

The GitHub-reported size is an early eligibility signal, not the sole protection. Compressed bytes, extracted bytes, and file count are independently bounded during acquisition.

## Compact append-oriented corpus

The default output is JSON Lines rather than one mutable JSON file per repository. Each line is a complete `ouroboros-index-record/v1` event.

Successful records contain:

- exact repository identity and stable GitHub repository ID;
- analyzer version/source revision and `canonical: true`;
- acquisition byte/file counts;
- file/LOC composition metrics;
- semantic composition metrics;
- category LOC and symbol counts;
- diagnostic counts and bounded diagnostic samples;
- representative scaffolding-inversion directories;
- representative deepest canonical semantic chains.

The compact record intentionally retains **both independent axes**:

1. how much repository acreage is product versus machinery/scaffolding;
2. how recursive/far-from-value that machinery becomes.

It does not collapse those into one moral grade.

The corpus does not store the entire semantic graph for every repository. Full scan artifacts can still be generated when detailed investigation is needed; the public corpus record is the lookup/ranking unit.

## Failure records

Once repository identity can be resolved, an ineligible or failed scan is also recorded with a machine-readable reason. Examples include:

- `repository-too-large`
- `archive-too-large`
- `extracted-too-large`
- `too-many-files`
- `unsafe-archive`
- `invalid-archive`
- `analysis-error`

Failures that occur before exact identity can be established carry the requested repository name and a null identity. Failed records do not count as completed identities, so later batches may retry them.

The CLI returns a nonzero exit code if any target fails. Skips are not failures.

## Bounded GitHub Actions batch

`.github/workflows/index-batch.yml` is a **manual** workflow for reproducible, small public batches. It accepts a manifest and an explicit target cap, records the workflow's analyzer SHA, and uploads the resulting JSONL corpus as an artifact.

It is intentionally not scheduled and it does not commit scan output back into the repository. This prevents the first ingestion train from turning Actions into a giant public-repository compute farm or creating thousands of tiny mutable result files.

The default Action batch is conservative because anonymous GitHub API requests are rate limited. Larger continuous indexing belongs behind a rate-aware authenticated or external worker design rather than an ever-growing Actions loop.

## What this train does not add

0.4 does not yet add repository discovery, GitHub namespace cursoring, a public Pages site, matched control cohorts, or longitudinal commit history. Those can now build on a real reusable ingestion unit instead of duplicating the inaugural-four workflow.
