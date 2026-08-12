# Core Rating and Capability Atlas 🐍

Ouroboros still starts with the number.

Version 0.12 reinforces the original quantitative front door and adds an optional Capability Atlas for a different question: **what externally meaningful things does this software appear to do, and where does their statically supported implementation live?**

Neither surface changes the existing measurement formula or turns Ouroboros into a quality grader.

## The shortest path: give me the rating

Use:

```bash
ouroboros /path/to/repository --rating-only
```

The command writes exactly one scalar to standard output: the original **file-level Ouroboros Index** on its existing 0–100 scale.

This mode deliberately performs only the baseline repository analysis needed to compute that original Index. It does **not** build the semantic graph merely to hide it afterward.

That makes the rating-only path suitable for shell scripts and other callers that only want the original number.

Example shape:

```text
7.8125
```

Use canonical rules when desired:

```bash
ouroboros /path/to/repository --canonical --rating-only
```

`--rating-only` cannot be combined with `--json`, `--report`, or `--quiet`: those modes either request additional output or duplicate the reason rating-only exists.

The ordinary command remains unchanged as the concise two-level explanation surface:

```bash
ouroboros /path/to/repository
```

The deeper reports, history, context, neighbors, and Anatomy Story remain optional.

## Capability Atlas: what does this software expose?

Run:

```bash
ouroboros-capabilities /path/to/repository
```

Save machine-readable evidence:

```bash
ouroboros-capabilities /path/to/repository --json capabilities.json
```

Write a self-contained HTML report:

```bash
ouroboros-capabilities /path/to/repository --report
```

or choose the output path:

```bash
ouroboros-capabilities /path/to/repository --report out/capabilities.html
```

Capability Atlas does not execute the target repository. It consumes the same static source scan and semantic evidence used elsewhere in Ouroboros.

## What counts as capability evidence

The first version deliberately starts with surfaces that can be supported by direct source or package evidence instead of guessing application intent from names.

It recognizes evidence including:

- Python `[project.scripts]`, `[project.gui-scripts]`, and Poetry script entry points;
- `package.json` command-line `bin` declarations;
- conventional Python `__main__`, Go `main`, Java `main`, and C# `Main` entry points when they can be anchored to a parsed symbol;
- common static HTTP route declarations in Python, JavaScript/TypeScript, C#, Java/Kotlin, and Rust;
- Python literal `__all__` exports;
- JavaScript/TypeScript explicit exports;
- explicit top-level public/exported declarations in C#, Java/Kotlin, Rust, and Go;
- high-confidence top-level symbols already classified by Ouroboros as user-surface code.

This is intentionally not a claim that those are the only ways software can expose capabilities. Reflection, generated wiring, dynamic registration, framework conventions, runtime plugin loading, declarative files Ouroboros does not yet understand, and unsupported languages can leave real capabilities undiscovered.

An absence of detected capabilities therefore means **supported static evidence was absent**, not that the software does nothing.

## Anchors and implementation neighborhoods

A discovered surface is first anchored to a semantic symbol when static evidence supports that mapping.

From that anchor, Capability Atlas follows outgoing semantic relationships with strict rules:

- only `EXACT` relationships enter the canonical implementation neighborhood;
- `PROBABLE` relationships are counted and retained as evidence but are not traversed;
- `UNRESOLVED` relationships remain unresolved and are not guessed;
- traversal is bounded to depth 4;
- each capability is bounded to 250 implementation symbols;
- discovery is bounded to 200 capability surfaces per run.

The bounds keep the output understandable and keep pathological graphs from turning one capability into the whole repository. A reached bound is reported explicitly.

A capability that can be discovered from direct configuration or source evidence but cannot be safely anchored to a semantic symbol remains **unanchored**. Ouroboros shows the declaration and stops there rather than inventing an implementation path.

## What a capability record contains

A capability can include:

- capability kind, such as CLI, HTTP route, public API, public symbol, or user surface;
- human-readable name;
- declaration path and line;
- exact semantic anchor when available;
- discovery evidence;
- implementation files reached through the bounded exact neighborhood;
- implementation symbols with source locations, roles, categories, and value distance;
- exact relationship evidence;
- counts of probable and unresolved relationships encountered without promoting them to canonical truth;
- a truncation flag when the implementation bound is reached.

The JSON is the complete evidence surface. The HTML report intentionally bounds very long relationship displays while keeping the full data in JSON.

## Public does not mean HTTP API

Language visibility is useful evidence, but it has limits.

A public C# class, exported Go identifier, or `pub` Rust item can be externally reusable without being a stable network endpoint or even an intended end-user feature. Capability Atlas labels these as **public symbols**, not automatically as product features, services, routes, or architectural boundaries.

That distinction is deliberate.

## Relationship to Repository Anatomy

Repository Anatomy asks:

> **Where does the code live, and what structural role does it play?**

Capability Atlas asks:

> **What externally meaningful doors can static evidence identify, and what exact implementation neighborhood lies behind each door?**

The two views share evidence but answer different questions.

Capability Atlas does not create a second Ouroboros score and does not alter the original rating.

## What this is not

Capability Atlas is not:

- a feature-quality score;
- an API design grader;
- an architecture-health assessment;
- an automated remediation system;
- a merge gate;
- a compliance or policy checker;
- a claim that an unobserved capability does not exist;
- a license to promote probable relationships to exact ones just to make a prettier path.

The purpose is visibility:

**show the software's statically evidenced doors, then show what exact evidence can justify behind those doors.**
