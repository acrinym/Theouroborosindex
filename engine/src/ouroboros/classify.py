from __future__ import annotations

import math
import re
from collections import defaultdict

from .model import Category, Component, Signal
from .scanner import ScannedFile


CATEGORY_RULES: dict[Category, tuple[str, ...]] = {
    Category.TESTING: ("test", "tests", "spec", "specs", "fixture", "fixtures", "mock", "mocks", "assert", "pytest", "unittest", "xunit", "nunit", "jest", "vitest"),
    Category.META_MACHINERY: ("meta-audit", "audit auditor", "audit of audit", "validator validator", "verify verifier", "check checker", "report validator", "quality of audit", "audit quality", "compliance of compliance", "tooling analyzer"),
    Category.AUDIT_PROVENANCE: ("audit", "auditor", "provenance", "receipt", "receipts", "evidence ledger", "reconcile", "reconciliation", "attestation", "traceability", "lineage record"),
    Category.VERIFICATION: ("verify", "verification", "validate", "validation", "validator", "integrity", "checksum", "consistency", "invariant", "sanity check", "precondition", "postcondition", "assertion"),
    Category.OBSERVABILITY: ("telemetry", "tracing", "trace", "metrics", "logging", "logger", "monitoring", "instrumentation", "diagnostic", "diagnostics", "span", "opentelemetry"),
    Category.PROCESS_MACHINERY: ("workflow", "pipeline", "ci", "cd", "release", "packaging", "deploy", "deployment", "quality gate", "approval gate", "build orchestration"),
    Category.DEVELOPER_TOOLING: ("tool", "tools", "generator", "scaffold", "scaffolding", "migration", "migrate", "bootstrap", "devtool", "codemod", "benchmark", "bench", "script", "scripts"),
    Category.USER_SURFACE: ("ui", "gui", "view", "views", "page", "pages", "screen", "dialog", "window", "controller", "route", "routes", "endpoint", "api", "cli", "command", "commands", "frontend", "component", "components", "interaction", "input", "menu"),
    Category.ESSENTIAL_SUPPORT: ("storage", "database", "repository", "persistence", "serializer", "serialization", "network", "http", "adapter", "adapters", "cache", "filesystem", "file system", "transport", "protocol", "config", "configuration", "loader", "parser"),
    Category.CORE_PRODUCT: ("gameplay", "game", "engine", "domain", "model", "models", "service", "services", "simulation", "render", "audio", "combat", "inventory", "session", "editor", "player", "business logic", "core"),
    Category.DOCUMENTATION: ("docs", "documentation", "readme", "guide", "manual", "tutorial", "architecture decision"),
}

PATH_PRIORITY = {
    Category.META_MACHINERY: 4.2, Category.AUDIT_PROVENANCE: 3.8, Category.TESTING: 4.0,
    Category.PROCESS_MACHINERY: 3.5, Category.OBSERVABILITY: 3.3, Category.VERIFICATION: 3.2,
    Category.USER_SURFACE: 2.9, Category.ESSENTIAL_SUPPORT: 2.5, Category.DEVELOPER_TOOLING: 2.8,
    Category.CORE_PRODUCT: 2.1, Category.DOCUMENTATION: 4.5,
}

MACHINERY_WORDS = {"audit", "verify", "validator", "validation", "receipt", "provenance", "telemetry", "diagnostic", "report", "reconcile", "checker", "monitor", "workflow", "pipeline"}


def normalized_tokens(value: str) -> set[str]:
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return set(re.findall(r"[a-z0-9]+", value.lower().replace("_", " ").replace("-", " ")))


def phrase_hits(haystack: str, phrases: tuple[str, ...]) -> list[str]:
    hits = []
    for phrase in phrases:
        if " " in phrase:
            if phrase in haystack:
                hits.append(phrase)
            continue
        if len(phrase) < 4:
            pattern = rf"\b{re.escape(phrase)}\b"
        else:
            pattern = rf"\b{re.escape(phrase)}\w*\b"
        if re.search(pattern, haystack):
            hits.append(phrase)
    return hits


def classify(scanned: ScannedFile, override: Category | None = None) -> Component:
    component = scanned.component
    if override is not None:
        component.category = override
        component.confidence = 1.0
        component.signals = [Signal(override, 10.0, "repository-declared path role")]
        return component

    path_lower = component.path.lower()
    content = scanned.text[:120_000].lower()
    path_tokens = normalized_tokens(component.path)
    flat_path = path_lower.replace("/", "").replace("_", "").replace("-", "").replace(" ", "")
    scores: dict[Category, float] = defaultdict(float)
    signals: list[Signal] = []

    if component.language in {"markdown", "documentation"}:
        scores[Category.DOCUMENTATION] += 7
        signals.append(Signal(Category.DOCUMENTATION, 7, "documentation file type"))
    if component.path.startswith(".github/"):
        scores[Category.PROCESS_MACHINERY] += 8
        signals.append(Signal(Category.PROCESS_MACHINERY, 8, "GitHub workflow/process path"))

    for category, phrases in CATEGORY_RULES.items():
        path_hits: list[str] = []
        for phrase in phrases:
            if " " not in phrase and len(phrase) < 4:
                if phrase in path_tokens:
                    path_hits.append(phrase)
            elif phrase.replace(" ", "") in flat_path:
                path_hits.append(phrase)
        if path_hits:
            weight = PATH_PRIORITY[category] + min(2.0, 0.35 * (len(path_hits) - 1))
            scores[category] += weight
            signals.append(Signal(category, weight, f"path signals: {', '.join(path_hits[:4])}"))
        content_hits = phrase_hits(content, phrases)
        if content_hits:
            density = min(3.6, 0.55 + math.log2(1 + len(content_hits)))
            scores[category] += density
            signals.append(Signal(category, density, f"content signals: {', '.join(content_hits[:5])}"))

    parts = path_tokens
    if {"tests", "test", "spec", "specs"} & parts:
        scores[Category.TESTING] += 5
        signals.append(Signal(Category.TESTING, 5, "test/spec directory structure"))
    if {"docs", "documentation"} & parts:
        scores[Category.DOCUMENTATION] += 5
        signals.append(Signal(Category.DOCUMENTATION, 5, "documentation directory structure"))
    if {"ui", "gui", "frontend", "views", "pages", "screens", "controllers", "routes"} & parts:
        scores[Category.USER_SURFACE] += 5
        signals.append(Signal(Category.USER_SURFACE, 5, "user-surface directory structure"))
    if {"src", "app", "game", "domain", "features"} & parts:
        scores[Category.CORE_PRODUCT] += 1.2
        signals.append(Signal(Category.CORE_PRODUCT, 1.2, "product-source directory structure"))

    machinery_mentions = sum(content.count(word) for word in MACHINERY_WORDS)
    recursive_phrases = (
        "audit report", "validate report", "verify report", "validate receipt", "verify receipt",
        "audit validator", "validator result", "verification result", "telemetry validator",
        "reconcile audit", "audit reconciliation", "checker result", "validate evidence",
    )
    recursive_hits = [phrase for phrase in recursive_phrases if phrase in content]
    if recursive_hits and machinery_mentions >= 4:
        weight = 4.5 + min(2.5, len(recursive_hits) * 0.6)
        scores[Category.META_MACHINERY] += weight
        signals.append(Signal(Category.META_MACHINERY, weight, f"recursive machinery semantics: {', '.join(recursive_hits[:4])}"))

    if scores.get(Category.TESTING, 0.0) >= 7:
        scores[Category.TESTING] += 4
    scores = defaultdict(float, {category: value for category, value in scores.items() if value > 0})
    if not scores:
        component.category = Category.UNKNOWN
        component.confidence = 0.0
        component.signals = []
        return component

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    category, best = ordered[0]
    second = ordered[1][1] if len(ordered) > 1 else 0.0
    margin = max(0.0, best - second)
    component.category = category
    component.confidence = min(0.99, 0.42 + 0.08 * best + 0.06 * margin)
    component.signals = sorted(signals, key=lambda s: s.weight, reverse=True)[:8]
    return component
