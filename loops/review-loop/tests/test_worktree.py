from __future__ import annotations

import subprocess
from pathlib import Path

from worktree import create_worktree, remove_worktree


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "f.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)


def test_create_and_remove_worktree(tmp_path):
    _init_repo(tmp_path)
    wt = create_worktree(tmp_path, "review-loop/test-run")
    assert wt.is_dir()
    assert (wt / "f.txt").is_file()
    out = subprocess.run(["git", "worktree", "list"], cwd=tmp_path,
                         capture_output=True, text=True).stdout
    assert ".rl-worktrees" in out
    remove_worktree(tmp_path, wt)
    assert not wt.exists()


def test_scratch_worktrees_are_self_ignored(tmp_path):
    # An orphaned .rl-worktrees dir (crash/kill → pruned registration) must NOT show as untracked and
    # block a merge — the loop self-ignores it, like integrate's .il-worktrees and fix's .fl.
    _init_repo(tmp_path)
    create_worktree(tmp_path, "review-loop/test-run")
    assert (tmp_path / ".rl-worktrees" / ".gitignore").read_text(encoding="utf-8").strip() == "*"
    # git must see nothing untracked under .rl-worktrees (the whole tree is ignored)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path,
                            capture_output=True, text=True).stdout
    assert ".rl-worktrees" not in status
