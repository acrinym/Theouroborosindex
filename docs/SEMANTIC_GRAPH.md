# Semantic Code Graph

Ouroboros 0.2 adds a language-neutral source graph beneath the repository-composition metrics. The baseline 0.1 file/LOC benchmark remains frozen so later semantic results can be compared with it.

## Invariant: target code is data

Indexing does **not execute target repository code**. Ouroboros parses source statically. It does not run `npm install`, `pip install`, `dotnet build`, project tests, repository hooks, shell scripts, or target binaries. The parser dependency belongs to Ouroboros, not to the repository being measured.

## Graph model

Each adapter emits the same vocabulary:

- symbols: file, namespace/module, class/interface/struct/enum/trait, function, method, constructor, property;
- relationships: contains, calls, imports, inherits, implements, references;
- resolution: exact, probable, unresolved;
- source location and inherited repository-composition category for every symbol.

Ouroboros resolves relationships across files, computes graph reachability from product symbols, assigns symbol-level Distance From Value, and walks reverse dependencies to expose real recursive machinery chains. An unresolved dynamic call remains unresolved; the Index does not invent a target to make the graph look complete.

### Canonical topology uses exact edges only

A probable relationship is evidence, not fact. Probable and unresolved edges stay in the graph and contribute to coverage statistics, but only `exact` relationships may:

- make a symbol product-reachable;
- change Distance From Value;
- create or lengthen a recursive machinery chain;
- contribute to canonical semantic depth or semantic Index.

A bare name match across programming languages is never exact. If a C# symbol happens to share a name with a Python symbol, for example, that textual coincidence remains `probable` at most. A canonical cross-language edge needs stronger evidence such as an explicit file dependency or a specialized adapter that understands the bridge.

The report exposes both an exact-resolution rate and an exact+probable resolvable rate. This prevents common-name guesses in large or polyglot repositories from manufacturing deep Ouroboros chains.

### Category seed versus topology

The 0.2 foundation inherits a symbol's initial composition category from its containing file so its topology can be compared directly with the frozen 0.1 classifier. The **structure is symbol-level now; the initial role label remains the 0.1 category seed**. A later symbol-role refinement can classify mixed-purpose methods/functions independently without changing the graph contract or rewriting the historical baseline.

## Language adapters

Python uses the standard-library `ast` parser. The scanner's other executable source languages use `tree-sitter-language-pack` through one grammar-tolerant adapter. That gives the Index a plugin boundary without forking its scoring model per language. The initial registry covers Python, JavaScript, TypeScript, C#, F#, Java, Kotlin, Go, Rust, Ruby, PHP, C, C++, Swift, Lua, PowerShell, and shell/Bash.

Language-specific adapters can later replace generic Tree-sitter extraction where a language needs deeper semantics—for example C# solution/project references, DI registration, ASP.NET routes, partial types, generated source, or proven cross-language bindings. They still emit the same graph contract.

## Semantic Index constants

The semantic Index uses the same transparent conceptual weights as the 0.1 Index, applied to symbol audit/meta share plus exact graph distance/depth. The weights are named public constants in `semantic/graph.py` and are fixed for an analyzer version. They are deliberately **not per-repository configuration**, so a repository cannot tune the scoring recipe to improve its own result. Changing the weights is an analyzer-version change and requires corpus provenance to record that version.

## Why both LOC and graph metrics stay

LOC describes repository mass. The semantic graph describes architectural role and connectivity. A huge isolated fixture can therefore remain large in LOC while having little graph centrality, while a small function reached from many product surfaces can be structurally important. The Index reports both rather than collapsing them into one opaque quality grade.
