# The Ouroboros Index

**Where did the product go?** 🐍

Ouroboros looks at a software repository and separates the thing people actually use from the machinery surrounding it: tests, tooling, verification, observability, audit/provenance, build/process code, and machinery around machinery.

The **Ouroboros Index** is the public, reproducible collection of those measurements. Every published record pins the repository commit and analyzer version used for the scan.

> A higher score is not automatically “bad code.” Tests, build systems, integrity checks, and operational tooling can be valuable. Ouroboros exists to make the tradeoff visible and to answer a simpler question: **how much of the repository is the product, and how far has the surrounding machinery grown?**

## Try it on a repository

Requires Python 3.10 or newer.

```bash
git clone https://github.com/acrinym/Theouroborosindex.git
cd Theouroborosindex
python -m pip install ./engine
ouroboros /path/to/your/repository
```

On Windows PowerShell:

```powershell
ouroboros C:\Repos\MyProject
```

Save the full machine-readable result with:

```bash
ouroboros /path/to/repo --json ouroboros.json
```

Use `--canonical` if you want the same rule as the public Index: ignore any `.ouroboros.json` supplied by the repository being measured.

## Start here

**[Read the User Guide](docs/USER_GUIDE.md)** for what the numbers mean, what to look at first, configuration, supported languages, and how to avoid misreading the score.

## What changed in 0.3

Ouroboros 0.3 keeps the original file/LOC view and adds a stricter symbol-level semantic view:

- mixed-purpose files can classify methods/functions independently instead of branding the whole file as one role;
- a same-named function in another file is no longer enough to manufacture an `EXACT` relationship;
- Python import bindings preserve qualified evidence such as `physics.resolve` and `pathlib.Path.resolve`;
- exact graph traversal is bounded and reports when the safety budget is reached;
- malformed or pathological files are isolated instead of aborting the whole repository scan;
- JSON output avoids non-standard `Infinity` values;
- the package is directly installable—no source reconstruction step is required.

The semantic layer is **static-only**. Target repository code is treated as data and is never executed.

## The inaugural benchmark

The frozen 0.1 cohort remains in [`results/inaugural-four/README.md`](results/inaugural-four/README.md). Semantic results and methodology are in [`results/inaugural-four/SEMANTIC.md`](results/inaugural-four/SEMANTIC.md) and [`docs/SEMANTIC_GRAPH.md`](docs/SEMANTIC_GRAPH.md).
