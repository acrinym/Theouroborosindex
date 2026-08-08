# Inaugural Ouroboros benchmark

The first public Ouroboros Index benchmark measures four functioning public software products with explicit AI/vibe-coding provenance. This is a deliberately high-signal inaugural cohort, **not a claim that these are mathematically the four most popular vibe-coded repositories on all of GitHub**.

Every repository was checked out at a frozen SHA and analyzed without per-project overrides or tuning using Ouroboros `0.1.0` from source head `8ae603829e5ca4be7b0961a5d9dd5d20393b837d`.

## Results

| Repository | Stars at selection | Product | Product+essential | Tooling | Audit | Meta | Scaffold/Product | Depth | Ouroboros |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ryokun6/ryos` | 1,223 | 75.6% | 78.0% | 22.0% | 0.2% | 0.0% | 0.29:1 | 2 | **5.1** |
| `srizzon/git-city` | 5,750 | 55.4% | 65.4% | 34.6% | 0.0% | 0.0% | 0.62:1 | 2 | **5.0** |
| `permissionlesstech/bitchat` | 34,736 | 41.0% | 47.3% | **52.7%** | 1.0% | 0.0% | **1.29:1** | 1 | **2.9** |
| `rdumasia303/deepseek_ocr_app` | 1,887 | **95.4%** | **95.4%** | 4.6% | 0.0% | 0.0% | 0.05:1 | 0 | **0.0** |

The table is ordered by Ouroboros Index, not by tooling share.

## Frozen inputs

- `permissionlesstech/bitchat` @ `1f59e814f90c3f489f48d68262cb1bf640bf6181`
- `srizzon/git-city` @ `bb4d9102af6126970bbce1fb3e20d818df4a535f`
- `rdumasia303/deepseek_ocr_app` @ `3dac0741b18afc934c063e8528e7576f4d63efe5`
- `ryokun6/ryos` @ `c599b3102900f20f66c48dff2b4562d07ddd52cf`

Stars are a selection-time popularity snapshot captured on 2026-08-07 and are not part of the Ouroboros score.

## Reproducibility

Accepted GitHub Actions run: [`31230688551`](https://github.com/acrinym/Theouroborosindex/actions/runs/31230688551).

Before each scan, the workflow reconstructs the runtime source and verifies every module against the original Git blob IDs from the Ouroboros implementation in `acrinym/Secretprojects`. The accepted run printed `Exact Ouroboros source verified against original Git blob IDs.` for every target.

Two earlier harness attempts failed before producing accepted scores because analyzer transport integrity checks failed. They are intentionally not part of the dataset.

No target emitted an Ouroboros classification warning in this run.

## Reading the numbers

`Tooling` and the `Ouroboros Index` are different signals. Bitchat has the highest tooling share and a scaffolding inversion, but most of that machinery is ordinary testing/tooling rather than recursive audit machinery. ryOS and Git City have lower tooling shares but reach dependency-backed machinery depth 2, which raises their Ouroboros Index.

An Ouroboros Index of `0.0` does **not** mean perfect code. It means this analyzer version found essentially none of the audit/meta/far-from-value signals that drive the index. DeepSeek OCR is simply extremely product-dense in this raw first pass.

## Raw-pass policy

This inaugural run deliberately applies no repository-specific `.ouroboros.json` role overrides. That prevents hand-tuning the benchmark after seeing the answer. Future analyzer versions may improve language and framework understanding; published records therefore always include both target SHA and analyzer version/head.
