from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .model import Category


def _normalize(value: str) -> str:
    normalized = value.replace("\\", "/")
    return normalized.removeprefix("./").rstrip("/")


@dataclass(slots=True)
class Config:
    overrides: dict[str, Category] = field(default_factory=dict)
    ignore: tuple[str, ...] = ()

    def category_for(self, relative_path: str) -> Category | None:
        normalized = _normalize(relative_path)
        best: tuple[int, Category] | None = None
        for prefix, category in self.overrides.items():
            candidate = _normalize(prefix)
            if normalized == candidate or normalized.startswith(candidate + "/"):
                length = len(candidate)
                if best is None or length > best[0]:
                    best = (length, category)
        return best[1] if best else None

    def ignored(self, relative_path: str) -> bool:
        normalized = _normalize(relative_path)
        return any(
            normalized == _normalize(prefix) or normalized.startswith(_normalize(prefix) + "/")
            for prefix in self.ignore
        )


def load_config(root: Path) -> Config:
    path = root / ".ouroboros.json"
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Ouroboros config {path}: {exc}") from exc

    overrides: dict[str, Category] = {}
    for category_name, paths in raw.get("paths", {}).items():
        try:
            category = Category(category_name)
        except ValueError as exc:
            raise ValueError(f"Unknown Ouroboros category in config: {category_name}") from exc
        for prefix in paths:
            overrides[str(prefix)] = category
    return Config(overrides=overrides, ignore=tuple(str(p) for p in raw.get("ignore", [])))
