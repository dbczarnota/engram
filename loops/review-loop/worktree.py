from __future__ import annotations

import subprocess
from pathlib import Path


def _slug(branch: str) -> str:
    return branch.replace("/", "-")


def create_worktree(repo_root: Path, branch: str) -> Path:
    # Deliberately neutral dir name: a "reviewloop"/"review-loop" path or branch makes the nested
    # agent read its own git context and confabulate a "review-loop harness" narrative (inventing
    # TASK.md, "planted bugs") instead of doing the review. See loops/review-loop + lessons.
    wt = repo_root / ".rl-worktrees" / _slug(branch)
    wt.parent.mkdir(parents=True, exist_ok=True)
    # Self-ignore the whole scratch-worktree dir in the TARGET repo so an orphaned worktree (left by a
    # crash/kill, its git registration pruned) never shows up as untracked and blocks a merge. Mirrors
    # integrate-loop's .il-worktrees and fix-loop's .fl — the loop cleans up after itself, no per-project
    # .gitignore needed. The `*` also ignores this file itself; `git clean -fd` (no -x) preserves it.
    (wt.parent / ".gitignore").write_text("*\n", encoding="utf-8")
    subprocess.run(["git", "worktree", "add", "-b", branch, str(wt)],
                   cwd=repo_root, check=True)
    return wt


def remove_worktree(repo_root: Path, worktree_path: Path) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree_path)],
                   cwd=repo_root, check=True)
