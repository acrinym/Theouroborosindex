# Value Paths — Ouroboros 0.13

Capability Atlas answers **what doors this software exposes**.

Value Paths asks the next question:

> **How does one statically supported action travel through the software?**

The first Value Paths release is intentionally strict. It does not try to reconstruct runtime execution from weak clues. It starts from a Capability Atlas surface that can be anchored to a semantic symbol and follows **EXACT `calls` relationships only**.

## List available capability doors

```bash
ouroboros-paths /path/to/repository --list
```

The list includes the stable capability id, kind, name, and semantic anchor. Unanchored capabilities remain visible in Capability Atlas but cannot become Value Paths until Ouroboros has exact evidence for an anchor.

## Trace one action

```bash
ouroboros-paths /path/to/repository --capability "Import project"
```

The selector accepts:

1. an exact capability id;
2. an exact capability name;
3. a unique substring of the id or name.

Ambiguous selectors are rejected instead of silently choosing one surface.

If the repository has exactly one anchored capability, `--capability` may be omitted.

## Save the evidence

```bash
ouroboros-paths /repo --capability demo --json value-path.json
ouroboros-paths /repo --capability demo --report value-path.html
```

The HTML report is self-contained. The JSON contains the complete selected path, retained alternatives, capability evidence, source locations, structural categories, and trust-boundary counts.

## What “strongest” means

Ouroboros needs a deterministic way to choose one representative path when an action branches.

For 0.13, the strongest path is selected by this transparent ordering:

1. longest bounded **EXACT simple call path**;
2. if tied, the path crossing more distinct files;
3. if still tied, the path crossing more distinct structural categories;
4. final ties use lexical symbol-id order for reproducibility.

This is **not** an importance score, architecture score, or quality judgment.

“Strongest” means only: **the most extensive exact call evidence observed under these rules.**

The default traversal bounds are:

- maximum call depth: 12;
- maximum graph expansions: 50,000;
- retained alternative terminal paths: 5.

A reached bound is reported explicitly.

## Why calls only?

The semantic graph also contains relationships such as:

- imports;
- references;
- containment;
- inheritance;
- interface implementation.

Those relationships are structurally useful, but they do not necessarily mean one user action flowed from one symbol into another.

Value Paths therefore refuses to turn them into action arrows simply to produce a richer-looking journey.

The canonical path uses:

```text
EXACT + CALLS
```

only.

## Trust boundaries remain visible

A symbol on the selected exact path can also contain calls that Ouroboros classified as:

- `PROBABLE`;
- `UNRESOLVED`.

Value Paths counts those call boundaries and reports them, but does not traverse them.

Example:

```text
command → handler → import_project → workspace.write
                         ├─ probable call: plugin hook
                         └─ unresolved call: framework-generated helper
```

The first line can be canonical when every arrow is exact. The other two remain evidence about the boundary rather than invented continuation.

## Alternatives

A real action can branch into several exact terminal paths.

Value Paths retains the next-best deterministic alternatives instead of pretending the selected representative is the only possible flow.

This is particularly useful when a handler performs several independent exact operations such as:

```text
handler → validate → parse → persist
handler → emit_notification
handler → render_result
```

The longest path may be selected as strongest while the other exact branches remain available in the same evidence package.

## Cycles

Call graphs can contain recursion or mutual calls.

Value Paths traces **simple paths**: a symbol is not revisited within the same candidate path. This prevents a real recursive relationship from becoming an artificial infinite journey.

## What a step contains

Each path step records:

- symbol id;
- symbol and qualified name;
- source path and line;
- symbol kind;
- structural category;
- existing Ouroboros value-distance measurement when available.

Each path edge records:

- source symbol;
- target symbol;
- relationship kind;
- exact source evidence retained by the semantic graph.

## Relationship to Capability Atlas

The product sequence is intentional:

```text
Capability Atlas: What does this software expose?
        ↓
Value Paths:      Where does one supported action go?
```

Value Paths reuses the capability door and semantic graph. It does not create a parallel feature-discovery engine.

## What this is not

Value Paths is not:

- dynamic tracing;
- profiling;
- target-code execution;
- a guarantee that every runtime branch is represented;
- a claim that the longest static call path is the most important business path;
- architecture grading;
- a merge recommendation;
- remediation;
- a policy or compliance gate.

Unsupported runtime wiring, reflection, dependency injection, generated code, callbacks, event buses, framework dispatch, or unresolved static relationships can create real runtime paths that are not canonical Value Paths yet.

Ouroboros says what the evidence supports and stops where the evidence stops.
