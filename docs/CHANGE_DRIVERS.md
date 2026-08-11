# Change Drivers

Ouroboros 0.9 answers the question that follows Bounded History: **what concretely moved when the repository anatomy changed?**

```bash
ouroboros-history /path/to/repo --from v1.0 --to HEAD --report
ouroboros-drivers /path/to/repo --before <commit-before> --after <event-commit> --report
```

`ouroboros-drivers` scans exactly two Git revisions using the same inert `git archive` transport and canonical rules as Bounded History. Target code, hooks, package managers, builds, and tests are never executed.

The result exposes:

- the largest changed, added, removed, or recategorized files by structural LOC movement;
- category-level LOC movement;
- existing structural explanations from the scan comparison;
- changes to the deepest EXACT semantic chains;
- exact before/after commit identity and archive acquisition counts.

A file is ranked highly when its categorized code mass moved substantially. A recategorized file counts its affected code mass even if its line count stayed the same, because the structural role changed.

These are **observed adjacent structural contributors**. Ouroboros does not call them developer blame, semantic causality beyond the compared snapshots, defects, or a quality score.

The JSON and self-contained HTML report contain no remote scripts, fonts, analytics, or telemetry.

## What this does not add

Change Drivers does not add a background watcher, commit crawler, policy engine, ownership scorer, blame ranking, remediation bot, or audit-of-audit layer. Bounded History finds the moment; Change Drivers explains the structural evidence around that moment.
