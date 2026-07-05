from __future__ import annotations

import re
from pathlib import Path

from config import ReviewLoopConfig

_UNCHECKED = re.compile(r"^\s*[-*]\s+\[ \]\s+(.*)$")
_MAX_ITEMS = 30


def _clean(text: str) -> str:
    return " ".join(text.replace("**", "").split())[:200]


def run_vault_todo_sweep(cfg: ReviewLoopConfig, repo_root: Path) -> tuple[list[str], list[str]]:
    """Surface the target project's open vault todos (report-only). Locates todos.md the same way the
    runner resolves report_dir. Never writes todos.md; never raises."""
    todos = (repo_root / cfg.report_dir).parent / "todos.md"
    if not todos.is_file():
        return ([], [])
    try:
        lines = todos.read_text(encoding="utf-8").splitlines()
    except Exception as e:  # defensive read boundary — never crash the run
        return ([], [f"vault-todo-sweep error: {e}"])
    items: list[str] = []
    for line in lines:
        m = _UNCHECKED.match(line)
        if not m:
            continue
        item = _clean(m.group(1))
        if item:
            items.append(item)
    errors: list[str] = []
    if len(items) > _MAX_ITEMS:
        errors.append(f"vault-todo-sweep: {len(items)} open items, showing first {_MAX_ITEMS}")
        items = items[:_MAX_ITEMS]
    return (items, errors)
