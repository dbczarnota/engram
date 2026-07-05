from __future__ import annotations

from pathlib import Path

from config import ReviewLoopConfig
from report import IterationResult


def make_iterate(scripted: list[IterationResult]):
    """Return an iterate fn that yields scripted results in order."""
    calls = {"n": 0}

    def iterate(cfg: ReviewLoopConfig, worktree: Path, iteration: int) -> IterationResult:
        i = calls["n"]
        calls["n"] += 1
        return scripted[i] if i < len(scripted) else IterationResult()

    return iterate
