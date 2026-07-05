from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FixLoopConfig:
    verify: dict[str, str]
    report_dir: str
    budget_tokens: int
    per_fix_cap: int = 60000
    max_files: int = 5
    # commands to bootstrap the project's environment inside the fix-loop's isolated worktree BEFORE any
    # verify runs (a bare git worktree has no `.venv`/`node_modules`, so pyright/pytest fail for env
    # reasons). e.g. {"deps": "uv sync"}. Empty = no setup needed.
    setup: dict[str, str] = field(default_factory=dict)
    # command that runs the suite with coverage and writes coverage.xml in the worktree; empty = disabled.
    coverage: str = ""


def load_fix_config(repo_root: Path) -> FixLoopConfig:
    """Reuse the repo's .reviewloop.yml (its `verify` block is the suite-green gate; report_dir/
    budget_tokens shared). A `fixloop:` section may override per_fix_cap / max_files. A top-level
    `setup:` block bootstraps the worktree environment before verify."""
    path = repo_root / ".reviewloop.yml"
    if not path.is_file():
        raise RuntimeError(f"no .reviewloop.yml in {repo_root}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    fl = data.get("fixloop") or {}
    return FixLoopConfig(
        verify=data.get("verify") or {},
        report_dir=str(data.get("report_dir") or "reports"),
        budget_tokens=int(data.get("budget_tokens") or 200000),
        per_fix_cap=int(fl.get("per_fix_cap") or 60000),
        max_files=int(fl.get("max_files") or 5),
        setup=dict(data.get("setup") or {}),
        coverage=str(data.get("coverage") or ""))
