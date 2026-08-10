# Ouroboros User Guide 🐍

Ouroboros answers one question:

> **Where did the product go?**

It scans a repository and shows how much of the code directly makes the app, game, service, tool, or user experience work—and how much exists around that product as support, tests, tooling, verification, observability, audit/provenance, or process machinery.

You do **not** need to understand the parser or graph implementation to use it.

## 1. Install it

You need Python 3.10 or newer.

```bash
git clone https://github.com/acrinym/Theouroborosindex.git
cd Theouroborosindex
python -m pip install ./engine
```

Then scan any repository or folder:

```bash
ouroboros /path/to/repository
```

Windows example:

```powershell
ouroboros C:\Repos\MyApp
```

The scanner reads source files. It does **not** run the target project's programs, tests, installers, hooks, scripts, package managers, or binaries.

## 2. Read the first screen

A normal scan prints two views.

### File / code view

This answers **where the repository's code mass went**.

- **Product code** — code classified as core product or user surface.
- **Product + support** — product plus essential infrastructure needed to make it work.
- **Surrounding machinery** — tests, developer tooling, observability, verification, audit/provenance, process machinery, and meta-machinery.
- **Scaffold / product** — machinery divided by direct product. `0.50:1` means roughly one line of machinery for every two product lines. `1.20:1` means machinery has become larger than the direct product. `n/a` means there was machinery but no direct product denominator to compare it with.
- **Audit + meta code** — the share specifically devoted to audit/provenance or machinery that exists around other machinery.
- **File-level depth** — the deepest dependency-backed machinery chain found from product code.
- **File-level Index** — the original 0–100 signal combining audit/meta share, distance from value, and recursive depth.

### Semantic view

This answers **what the code is structurally doing** at the level of functions, methods, classes, and relationships.

- **Product symbols** — product-facing functions/methods/classes.
- **Machinery symbols** — test/tooling/verification/audit/process symbols.
- **Exact relationships** — call/import/inheritance relationships Ouroboros has enough static evidence to trust for canonical topology.
- **Resolvable links** — exact plus probable relationships. Probable links are visible evidence but do not get to manufacture canonical depth.
- **Recursive depth** — the deepest exact machinery chain leading away from product value.
- **Semantic Index** — the same basic Ouroboros idea applied to symbol roles and exact topology.

## 3. Do not treat the Index like a grade

A score of 8 is not automatically worse than a score of 3.

A repository can legitimately have a lot of tests. A safety-sensitive updater can legitimately verify checksums. A compiler can legitimately contain substantial tooling. The useful question is whether the surrounding machinery is proportionate to the thing being built and whether machinery has begun to exist mostly for other machinery.

A useful reading order is:

1. Look at **Product**, **Product + support**, and **Scaffold / product**.
2. Compare **machinery share** with **audit/meta share**. A test-heavy repo is different from an audit-heavy repo.
3. Look at **recursive depth**.
4. Inspect the exact chains before deciding anything needs to be removed.
5. Check **exact relationship coverage**. Low coverage means the semantic picture is incomplete, not that the repository is clean or dirty.

## 4. What the categories mean

| Category | Plain-English meaning |
|---|---|
| Core product | Main behavior the product exists to provide |
| User surface | UI, CLI, routes, screens, commands, and direct interaction code |
| Essential support | Storage, configuration, parsers, networking, adapters, persistence, and similar support |
| Developer tooling | Scripts, generators, migrations, probes, benchmarks, scaffolding |
| Testing | Tests, specs, fixtures, mocks, test harnesses |
| Observability | Logging, telemetry, tracing, diagnostics, monitoring |
| Verification | Validation, integrity checks, checksums, invariants |
| Audit / provenance | Receipts, audit records, provenance, reconciliation, traceability |
| Process machinery | CI/CD, workflows, release/deployment/build orchestration |
| Meta-machinery | Machinery whose subject is other machinery |
| Documentation | Readmes, guides, docs |
| Unknown | Supported text/code that does not have enough evidence for a useful role |

Mixed-purpose files are handled more carefully in 0.3. A file containing an integrity helper no longer automatically turns every unrelated method in that file into verification code; strong symbol-local evidence can assign different roles inside the same file.

## 5. Save a full result

```bash
ouroboros /path/to/repo --json result.json
```

The JSON contains the file-level analysis, semantic graph, relationship resolutions, diagnostics, symbol roles, and exact chains.

The writer uses strict JSON: undefined ratios are emitted as `null`, never non-standard `Infinity`.

## 6. Optional local configuration

For your own scans, you can place `.ouroboros.json` at the repository root when Ouroboros needs project-specific context.

```json
{
  "paths": {
    "core-product": ["src/game"],
    "user-surface": ["src/ui"],
    "testing": ["tests"]
  },
  "ignore": ["examples/generated"]
}
```

The longest matching path wins.

Repository-provided configuration is useful for a developer analyzing their own code, but it would also make public rankings gameable. The public Ouroboros Index therefore uses the **canonical** view and ignores target-authored overrides. Reproduce that locally with:

```bash
ouroboros /path/to/repo --canonical
```

## 7. EXACT, PROBABLE, and UNRESOLVED

**EXACT** means Ouroboros has structural evidence strong enough to let that relationship affect Distance From Value and recursive depth.

Examples include a same-file method call or a qualified imported Python call such as `physics.resolve` that matches the imported module and symbol.

**PROBABLE** means there is a plausible target but not enough proof. A unique function named `resolve` in some other Python file is still only probable if the call site did not actually identify that module.

**UNRESOLVED** means static analysis could not identify a safe target. Reflection, dynamic dispatch, dependency injection, macros, runtime plugin loading, and generated wiring can legitimately remain unresolved.

Ouroboros would rather leave an edge unresolved than invent a dramatic audit chain from a coincidental function name.

## 8. If the score looks surprising

First check:

- **Role mix:** Is the repo mostly tests or verification rather than recursive audit machinery?
- **Exact coverage:** Is the semantic graph seeing enough of the language/framework to support a strong conclusion?
- **Exact chains:** Do the reported chains make architectural sense when you read the named functions/files?

If a chain is clearly false, that is a classifier/resolver bug worth fixing in Ouroboros. Do not “fix” the target repository merely to make the score prettier.

## 9. Supported source languages

The scanner recognizes Python, JavaScript, JSX, TypeScript, TSX, C#, F#, Java, Kotlin, Go, Rust, Ruby, PHP, C, C++, Swift, Lua, PowerShell, shell/Bash, SQL, HTML, CSS/SCSS, Markdown/RST, YAML, TOML, JSON, and XML.

The semantic graph currently has direct AST/Tree-sitter adapters for Python, JavaScript, TypeScript, TSX, C#, F#, Java, Kotlin, Go, Rust, Ruby, PHP, C, C++, Swift, Lua, PowerShell, and shell/Bash. Other recognized files still contribute to the file-level view.

## 10. What Ouroboros deliberately does not do

Ouroboros is not a security scanner, style linter, compliance framework, AI-authorship detector, or generic “code quality” score.

It does not tell you whether the repository is good. It tells you **what the repository is spending its complexity budget on**.
