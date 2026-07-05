from __future__ import annotations

import subprocess
from pathlib import Path


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def open_bundle(repo: Path, name: str, ref: str = "master") -> Path:
    wt = repo / ".il-worktrees" / name.replace("/", "-")
    wt.parent.mkdir(parents=True, exist_ok=True)
    (wt.parent / ".gitignore").write_text("*\n", encoding="utf-8")   # never track the scratch worktrees
    if wt.exists():
        _git(repo, "worktree", "remove", "--force", str(wt))
    # detached at `ref`'s commit (default master) — an anonymous integration head we build merges onto
    _git(repo, "worktree", "add", "--detach", str(wt), ref)
    return wt


def head_sha(bundle_wt: Path) -> str:
    """The bundle's current HEAD — captured BEFORE a merge so a rejected fix is reverted to the exact
    prior GREEN state (not `HEAD~1`, which under-reverts a fast-forwarded multi-commit fix branch and
    would leave rejected commits inside a 'green' published bundle)."""
    return _git(bundle_wt, "rev-parse", "HEAD").stdout.strip()


def try_merge(bundle_wt: Path, fix_branch: str) -> bool:
    # --no-ff: always create a merge commit so the bundle history is explicit (never a fast-forward that
    # swallows the fix's commits into the head). Revert still uses the captured pre-merge sha, not HEAD~1.
    proc = _git(bundle_wt, "merge", "--no-ff", "--no-edit", fix_branch)
    if proc.returncode == 0:
        return True
    _git(bundle_wt, "merge", "--abort")   # leave the bundle at its prior clean state
    return False


def revert_last(bundle_wt: Path, to_sha: str) -> None:
    """Reset the bundle back to `to_sha` (the pre-merge GREEN state) and clean — robust to fast-forward
    and multi-commit fix branches, unlike a positional `HEAD~1`."""
    _git(bundle_wt, "reset", "--hard", to_sha)
    _git(bundle_wt, "clean", "-fd")


def finalize(repo: Path, bundle_wt: Path, branch: str) -> str | None:
    head = _git(bundle_wt, "rev-parse", "HEAD").stdout.strip()
    master = _git(repo, "rev-parse", "master").stdout.strip()
    if not head or head == master:
        return None                       # nothing merged -> no bundle
    _git(repo, "branch", "-f", branch, head)
    return head


def close_bundle(repo: Path, bundle_wt: Path) -> None:
    _git(repo, "worktree", "remove", "--force", str(bundle_wt))
    _git(repo, "worktree", "prune")
