# Data Journey

Ouroboros 0.17 adds **Data Journey**: choose one class, struct, type, interface, enum, model-like object, or schema-like symbol and see where the current static evidence places it in a lifecycle.

The central question is:

> **Where is this thing created, transformed, persisted, and emitted?**

Data Journey is deliberately different from Value Paths. Value Paths follows an action through an exact call chain. Data Journey groups evidence around one selected data symbol.

## Usage

List selectable data-shaped symbols:

```bash
ouroboros-data /path/to/repo --list
```

Follow one symbol:

```bash
ouroboros-data /path/to/repo --data Record
```

Save machine-readable evidence and a self-contained report:

```bash
ouroboros-data /path/to/repo --data Record --json record-journey.json --report record-journey.html
```

Use `--canonical` to ignore repository-authored `.ouroboros.json` classification overrides, matching the public Index posture.

## Evidence contract

A canonical Data Journey **event requires an `EXACT` `CALLS` relationship** in the semantic graph.

Two event forms are currently recognized:

1. **Creation** — an exact call resolves directly to the selected class/struct/type/interface/enum symbol.
2. **Lifecycle member call** — an exact call resolves to a member exactly contained by the selected data symbol, and the member name carries a recognized lifecycle verb.

Lifecycle member names are grouped descriptively:

- **created** — constructors and names such as `create`, `build`, `parse`, `load`, `hydrate`, or `deserialize`;
- **transformed** — names such as `transform`, `map`, `normalize`, `convert`, `merge`, or `enrich`;
- **persisted** — names such as `save`, `store`, `write`, `insert`, `persist`, `commit`, or `serialize`;
- **emitted** — names such as `emit`, `publish`, `send`, `output`, `export`, `render`, or `dispatch`.

The relationship and the lifecycle role have different trust semantics. The call itself must be exact. A lifecycle role inferred from a member name is explicitly labeled as name-derived instead of being presented as a proven runtime effect.

## Boundaries are not events

Data Journey also lists **lifecycle-shaped member definitions** on the selected type. This answers a useful second question: *what lifecycle doors does this data type expose?*

A defined `save()` method with no exact caller is not counted as a persistence event. It remains a boundary definition until supported call evidence reaches it.

This distinction prevents unused methods, dead branches, or unresolved dynamic calls from being turned into fake lifecycle activity.

## Not runtime chronology

The report displays the lifecycle in the human-readable order:

`created → transformed → persisted → emitted`

That ordering is a lifecycle grouping, **not a claim that the program executes those events in that order**. Data Journey does not currently claim object identity across calls or reconstruct a dynamic runtime trace.

If `record.save()` remains probable or unresolved, Ouroboros does not promote it. If `Record.save(record)` resolves exactly to the selected type's contained member, it can become a canonical event with the role inference separately disclosed.

## Product boundary

Data Journey does not:

- execute target code;
- invent object identity across functions;
- promote probable or unresolved calls into canonical flow;
- judge architecture quality;
- recommend refactors;
- treat lifecycle-shaped method names as proof of side effects;
- create policy, compliance, audit, or remediation machinery.

It is another descent from the Ouroboros number into visible software structure: **follow the thing, not the function.**
