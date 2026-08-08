# Semantic Code Graph

Ouroboros 0.2 adds a language-neutral source graph beneath the repository-composition metrics.
The baseline 0.1 file/LOC benchmark remains frozen so later semantic results can be compared with it.

## Invariant: target code is data

Indexing does **not execute target repository code**. Ouroboros parses source statically. It does not run
`npm install`, `pip install`, `dotnet build`, project tests, repository hooks, shell scripts, or target binaries.
The parser dependency belongs to Ouroboros, not to the repository being measured.

## Graph model

Each adapter emits the same vocabulary:

- symbols: file, namespace/module, class/interface/struct/enum/trait, function, method, constructor, property;
- relationships: contains, calls, imports, inherits, implements, references;
- resolution: exact, probable, unresolved;
- source location and inherited repository-composition category for every symbol.

Ouroboros resolves relationships across files, computes graph reachability from product symbols, assigns
symbol-level Distance From Value, and walks reverse dependencies to expose real recursive machinery chains.
An unresolved dynamic call remains unresolved; the Index does not invent a target to make the graph look complete.

## Language adapters

Python uses the standard-library `ast` parser. The scanner's other executable source languages use
`tree-sitter-language-pack` through one grammar-tolerant adapter. That gives the Index a plugin boundary without
forking its scoring model per language. The initial registry covers Python, JavaScript, TypeScript, C#, F#, Java,
Kotlin, Go, Rust, Ruby, PHP, C, C++, Swift, Lua, PowerShell, and shell/Bash.

Language-specific adapters can later replace the generic Tree-sitter extraction where a language needs deeper
semantics (for example C# solution/project references, DI registration, ASP.NET routes, partial types, or generated
source). They still emit the same graph contract.

## Why both LOC and graph metrics stay

LOC describes repository mass. The semantic graph describes architectural role and connectivity. A huge isolated
fixture can therefore remain large in LOC while having little graph centrality, while a small function reached from
many product surfaces can be structurally important. The Index reports both rather than collapsing them into one
opaque quality grade.
