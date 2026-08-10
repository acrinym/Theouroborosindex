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

0.3 uses an asymmetric refinement rule:

- strong architectural paths such as tests, audit/provenance, logging/telemetry, workflows, validators, and tooling are authoritative;
- a product/support symbol is not promoted into machinery merely because its business-domain vocabulary includes words such as `build`, `pipeline`, `receipt`, `verify`, `metrics`, or `bootstrap`;
- a neutral-path file already classified as machinery can be split locally: symbols with strong local machinery evidence keep that role, while unrelated symbols fall back to product or essential support according to architectural context.

This means an `IntegrityStore.verify()` method can remain verification while an unrelated `LibraryInspector.images()` method in the same module can be essential support.

## Two semantic axes

**Machinery share** and **scaffolding ratio** count testing and developer tooling because those symbols really do surround the product.

The semantic Index's **far-from-value term** is narrower. It counts only far symbols in recursive machinery categories:

- observability;
- verification;
- audit/provenance;
- process machinery; and
- meta-machinery.

Ordinary tests and generic developer tooling do not automatically increase the far-distance term. This preserves the intended distinction between a repository with extensive assurance/tooling and one where machinery has begun supporting, checking, measuring, or governing other machinery.

## Bounded traversal

File-level and semantic recursive-chain searches have explicit expansion budgets. If a graph reaches the limit, the result reports truncation rather than pretending its observed maximum depth is complete.

The canonical recursive-depth search itself follows EXACT relationships only. Probable candidates cannot manufacture depth.

## Coverage

The semantic report exposes exact relationship rate, exact + probable resolvable rate, parser diagnostics, product-reachable symbols, far-recursive-machinery share, recursive depth, expansion count, and whether traversal was truncated.

Low coverage is uncertainty, not a low-score guarantee.

## Version policy

The semantic Index weights are fixed public constants for an analyzer version. They are deliberately **not** repository-configurable because public scores must remain comparable and resistant to score tuning.

Changing the scoring formula, trust semantics, or role model requires an analyzer-version change so corpus records remain reproducible.

0.3 is such a version change: symbol-local roles, stricter exact-resolution semantics, and the recursive-distance correction intentionally mean old 0.2 semantic scores are historical rather than directly interchangeable.
