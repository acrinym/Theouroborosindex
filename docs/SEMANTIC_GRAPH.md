# Semantic Graph Contract

Ouroboros 0.3 keeps the frozen file/LOC composition view and adds a language-neutral static source graph for functions, methods, types, imports, calls, inheritance, and implementation relationships.

## Trust rule

Target code is data. Ouroboros never executes the repository being measured.

Canonical topology uses **EXACT** relationships only. Probable and unresolved relationships remain visible for coverage and diagnosis but cannot create product reachability, Distance From Value, recursive depth, or the semantic Index.

### Exact proof became stricter in 0.3

A matching name is not enough.

- Same-scope and unambiguous same-file bare references can be exact.
- A bare name in another file is at most probable, even if it is unique.
- Qualified references may be exact when their module/type qualification matches a local symbol.
- Python import aliases are preserved, so `from physics import resolve; resolve()` becomes a qualified `physics.resolve` reference.
- `Path(...).resolve()` imported from `pathlib` therefore remains `pathlib.Path.resolve`; it cannot silently bind to some unrelated local function named `resolve`.
- File import edges must match the import target as well as a dependency candidate. The dependency set alone cannot fabricate an exact import.
- A bare same-name match across languages is never exact.

## Symbol-local roles

0.2 inherited every symbol role from its containing file. That overclassified mixed-purpose modules.

0.3 retains strong file/path evidence for clearly dedicated areas such as tests, audit files, workflows, or GUI surfaces, then refines neutral mixed-purpose files at symbol level. Strong names and local bodies can identify verification, audit, observability, tooling, user-surface, or essential-support behavior independently.

This means an `IntegrityStore.verify()` method can remain verification while an unrelated `LibraryInspector.images()` method in the same module can be essential support.

## Bounded traversal

File-level and semantic recursive-chain searches have explicit expansion budgets. If a graph reaches the limit, the result reports truncation rather than pretending its observed maximum depth is complete.

## Coverage

The semantic report exposes exact relationship rate, exact + probable resolvable rate, parser diagnostics, product-reachable symbols, far-from-value share, recursive depth, and whether traversal was truncated.

Low coverage is uncertainty, not a low-score guarantee.

## Version policy

The semantic Index weights are fixed public constants for an analyzer version. Changing the scoring formula, trust semantics, or role model requires an analyzer-version change so corpus records remain reproducible.

0.3 is such a version change: symbol-local roles and stricter exact-resolution semantics intentionally mean old 0.2 semantic scores are historical rather than directly interchangeable.
