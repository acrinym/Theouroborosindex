# Bounded History

Ouroboros 0.8 answers the temporal question that current-state anatomy and two-scan comparison cannot answer by themselves:

> **When did this structural change happen?**

It does that without becoming a crawler, background service, repository executor, or history-sampling guesser.

## Basic use

```bash
ouroboros-history /path/to/repo --from v1.0.0 --to HEAD
```

Write machine-readable history data and a self-contained report:

```bash
ouroboros-history /path/to/repo \
  --from v1.0.0 \
  --to HEAD \
  --json ouroboros-history.json \
  --report
```

The default report is `ouroboros-history.html`.

## What it traverses

History mode follows the local repository's **first-parent history** from `--from` through `--to`, inclusive.

Every commit in that bounded range is scanned. There is no checkpoint sampling and no bisection assumption.

The default maximum is 50 commits. You can raise it deliberately:

```bash
ouroboros-history . --from <old-ref> --to HEAD --max-commits 100
```

The hard maximum is 200 commits.

If the requested range does not fit within the selected bound, Ouroboros refuses the run. It does **not** silently inspect every fifth commit, interpolate a crossover, or claim an exact change point from sampled history.

## Why first-parent only

A repository can contain merge-side histories that are not part of the main line being inspected. 0.8 intentionally keeps the question simple and reproducible:

- follow one explicit line of development;
- scan every commit on that line;
- identify the commit where the observed structure changed.

If `--from` is not on the first-parent chain ending at `--to`, the command fails with an explicit boundary error.

Future work can add other traversal modes only if they preserve the same truthfulness about what history was actually inspected.

## Target safety

Historical snapshots are obtained with:

```text
git archive <commit>
```

Ouroboros then safely extracts regular files into a temporary directory and runs the existing static analyzer over those inert files.

History mode does **not**:

- check out historical commits into the target worktree;
- execute target code;
- execute target hooks;
- run package managers, build systems, tests, or generated scripts;
- access the network;
- honor target-authored `.ouroboros.json` overrides.

History scans are always canonical so the measurement rules do not change just because an older commit carried a different repository-local override.

Symlink and special archive members are skipped instead of followed. Their counts are recorded in checkpoint acquisition metadata.

## Change points reported

0.8 deliberately reports a small set of structural events instead of inventing a general-purpose historical policy engine.

### Repository balance shift

A commit is marked when the repository-level relationship between direct product share and surrounding machinery share changes, such as:

```text
product-dominant → machinery-dominant
```

The event includes the before/after shares and the exact commit where the observed shift first appears in the scanned first-parent sequence.

### Directory crossover

The existing saved-scan comparison primitive already identifies directories that move from:

```text
product_lines > machinery_lines
```

to:

```text
machinery_lines > product_lines
```

Bounded History applies that same primitive to each consecutive pair of commits and pins the crossover to the later commit.

### Exact recursive-depth change

When canonical exact recursive depth changes between adjacent commits, the event records the old depth, new depth, delta, and commit.

No PROBABLE relationship is promoted into canonical topology to make history look more complete.

## Timeline checkpoints

Each scanned commit records a compact checkpoint containing:

- exact commit SHA;
- authored timestamp;
- commit subject;
- direct product share;
- machinery share;
- scaffold/product ratio;
- exact recursive depth;
- Semantic Index;
- exact relationship coverage, or `n/a` when there were zero relationships;
- inversion count;
- anatomy fingerprint;
- archive file/byte counts and skipped-link counts;
- warning and semantic-diagnostic counts.

The report highlights commits that contain tracked structural events.

## Relationship to `ouroboros-compare`

`ouroboros-compare` remains the right tool when you already have two saved scans and want a detailed before/after explanation.

`ouroboros-history` is the bounded temporal companion:

1. scan each commit in an explicit first-parent range;
2. reuse the existing comparison semantics between adjacent commits;
3. identify the commit where a crossover or exact-depth change appears.

The history command does not replace saved-scan comparison and does not create a second anatomy model.

## Scope boundaries

0.8 does not add:

- automatic remote repository crawling;
- recurring scheduled history scans;
- a server or database;
- GitHub-wide commit discovery;
- heuristic sampling presented as exact history;
- a quality leaderboard;
- policy or governance gates;
- target execution;
- analyzer self-analysis loops;
- drones, wings, targeting systems, or other unnecessary aviation equipment. 🐍
