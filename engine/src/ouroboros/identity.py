from __future__ import annotations

import re
from pathlib import Path

_HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")


def static_git_sha(root: str | Path) -> str | None:
    """Resolve HEAD by reading Git metadata only; never execute target repository code."""
    root_path = Path(root).expanduser().resolve()
    git_entry = root_path / ".git"
    git_dir = git_entry
    try:
        if git_entry.is_file():
            first = git_entry.read_text(encoding="utf-8", errors="replace").strip()
            if not first.lower().startswith("gitdir:"):
                return None
            git_dir = (root_path / first.split(":", 1)[1].strip()).resolve()
        if not git_dir.is_dir():
            return None
        head = (git_dir / "HEAD").read_text(encoding="utf-8", errors="replace").strip()
        if _HEX40.fullmatch(head):
            return head.lower()
        if not head.startswith("ref:"):
            return None
        ref = head.split(":", 1)[1].strip()
        loose = git_dir / ref
        if loose.is_file():
            value = loose.read_text(encoding="utf-8", errors="replace").strip()
            return value.lower() if _HEX40.fullmatch(value) else None
        packed = git_dir / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line or line.startswith(("#", "^")):
                    continue
                try:
                    value, name = line.split(" ", 1)
                except ValueError:
                    continue
                if name.strip() == ref and _HEX40.fullmatch(value):
                    return value.lower()
    except OSError:
        return None
    return None
