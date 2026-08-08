# The Ouroboros Index

**Where did the product go?** 🐍

The Ouroboros Index is a public, reproducible corpus of repository-composition measurements produced by Ouroboros. It measures how much software is direct product, essential support, tests/tooling, verification, audit/provenance, process machinery, and machinery around machinery.

Scores are descriptive signals, not quality grades. Every indexed record pins the repository SHA and analyzer version used for the measurement.

The inaugural benchmark targets four public, functioning projects with explicit AI/vibe-coding provenance.

## Two views of the repository

- **Ouroboros 0.1** measures file/LOC composition and file-level topology.
- **Ouroboros 0.2 semantic** parses real source structure into symbols and call/import/inheritance relationships, then derives exact graph Distance From Value and recursive machinery depth.

The semantic layer is static-only: target repository code is treated as data and is never executed.

See [`results/inaugural-four/README.md`](results/inaugural-four/README.md) for the frozen 0.1 baseline and [`results/inaugural-four/SEMANTIC.md`](results/inaugural-four/SEMANTIC.md) for the first symbol-level comparison. Machine-readable semantic records live in [`results/inaugural-four/semantic-index.json`](results/inaugural-four/semantic-index.json).
