# Evolution Movie / Anatomy Time Machine

Ouroboros 0.14 turns the existing Repository Anatomy and Bounded History evidence into a self-contained time-axis visualization.

The command is:

```bash
ouroboros-movie /path/to/repo --from v1.0.0 --to HEAD --report
```

Optional machine-readable output can be written alongside it:

```bash
ouroboros-movie /path/to/repo \
  --from v1.0.0 \
  --to HEAD \
  --json ouroboros-evolution-movie.json \
  --report ouroboros-evolution-movie.html
```

## What a frame means

Every frame is one actual first-parent commit in the requested bounded range. Ouroboros:

1. resolves the exact commit SHA;
2. obtains the tree with `git archive`;
3. extracts it into a temporary inert snapshot;
4. performs the same canonical static scan used by Bounded History;
5. applies the same deterministic `spatial_layout` used by Repository Anatomy;
6. records the existing composition, exact recursive depth, Semantic Index, coverage, anatomy fingerprint, diagnostics, and archive provenance;
7. compares the map to the immediately preceding frame.

There is no interpolation pretending to be measurement. The slider moves between scans that actually happened.

## Transition evidence

For each adjacent pair, the movie records file-level structural facts independently:

- appeared;
- disappeared;
- grew in code-line mass;
- shrunk in code-line mass;
- changed Ouroboros category;
- changed canonical value distance.

One file can carry several flags at once. For example, a file can grow and move from `essential-support` to `core-product` in the same transition.

The first frame is explicitly marked as a baseline. Ouroboros does **not** compare it with an imaginary empty repository and claim that every file “appeared.”

Existing Bounded History events are also retained, including repository dominance shifts, directory crossovers, and exact recursive-depth changes.

## Interactive report

The self-contained HTML report provides:

- a commit scrubber;
- play/pause playback;
- selectable playback speed;
- the deterministic repository treemap for the selected frame;
- current product/machinery shares;
- exact recursive depth and Semantic Index;
- exact relationship coverage when meaningful;
- mapped-file count;
- transition counts and exact changed paths;
- Bounded History event markers tied to their commit.

The report contains its evidence payload directly and loads no remote scripts, fonts, styles, analytics, or telemetry.

## Trust and execution boundary

Evolution Movie does not broaden the existing Bounded History trust model.

- traversal is first-parent only;
- the range is inclusive and exact;
- every commit in the accepted range is scanned;
- oversized ranges are refused rather than sampled and presented as exact;
- target-authored `.ouroboros.json` overrides are ignored;
- target code is never executed;
- hooks, tests, package managers, builds, submodules, and target network behavior are never run;
- historical transport remains `git archive`;
- canonical topology remains EXACT-only;
- motion, color, and size are descriptions of structure, not quality judgments.

## What 0.14 does not do

Evolution Movie is not:

- a quality score;
- a merge gate;
- an architecture-health verdict;
- a changelog generator;
- a remediation engine;
- a policy or compliance system;
- a remote repository crawler;
- a scheduled monitoring service;
- an invented runtime trace.

It visualizes structural evidence Ouroboros already knows how to measure.

**The repository is the subject. Git supplies the time axis. The Ouroboros rating remains the head of the snake.**
