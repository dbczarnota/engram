from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def _git(wt: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=wt, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def wip_branch(fingerprint: str) -> str:
    """Deterministic `wip/<slug>-<hash>` name for a needs-human finding's preserved last attempt. Computed
    the SAME way in the orchestrator (which creates it) and the runner (which links it in the dossier), so
    no return-signature plumbing is needed."""
    slug = "".join(c if c.isalnum() else "-" for c in fingerprint)[:30].strip("-")
    h = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:8]
    return f"wip/{slug}-{h}"


def branch_exists(wt: Path, name: str) -> bool:
    proc = subprocess.run(["git", "rev-parse", "--verify", "--quiet", name],
                          cwd=wt, capture_output=True, text=True)
    return proc.returncode == 0


# Build/tool artifacts the loop ITSELF generates by running verify (pytest/ruff/pyright) inside the
# worktree. They must never count as a code change (blast-radius, rich-bug's test-only check,
# suite_is_clean) nor get committed onto a fix branch — regardless of whether the target repo happens to
# gitignore them. (A target repo that omits `__pycache__/` from its .gitignore otherwise trips the loop.)
_ARTIFACT_DIR_MARKERS = ("__pycache__/", ".pytest_cache/", ".ruff_cache/", ".mypy_cache/")
_ARTIFACT_SUFFIXES = (".pyc", ".pyo")
# coverage data files (e.g. from `pytest --cov`): `.coverage`, `.coverage.<host>.<pid>`
_ARTIFACT_BASENAMES = (".coverage",)


def _is_artifact(path: str) -> bool:
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if p.endswith(_ARTIFACT_SUFFIXES) or any(m in p for m in _ARTIFACT_DIR_MARKERS):
        return True
    return base == ".coverage" or base.startswith(".coverage.")


def _stage_non_artifacts(wt: Path) -> None:
    """Stage every change except build/tool artifacts, so a fix commit never carries `__pycache__/*.pyc`
    etc. Stage-all then unstage the artifacts (robust to renames/deletes that a path-list `git add`
    would mishandle). Callers MUST be guarded by a `changed_files`/`suite_is_clean` check (same
    `_is_artifact` predicate) so the resulting commit is never empty. `-z` + `core.quotePath=false` keep
    non-ASCII / whitespace paths intact so the unstage pathspec actually matches them."""
    _git(wt, "add", "-A")
    out = _git(wt, "-c", "core.quotePath=false", "diff", "--cached", "--name-only", "-z")
    for name in out.split("\0"):
        if name and _is_artifact(name):
            _git(wt, "reset", "-q", "HEAD", "--", name)


def ensure_scratch(wt: Path) -> None:
    """Create the `.fl/` scratch dir and gitignore its whole contents, so agent prompt files never get
    staged by `git add -A` (commit leak) nor counted by `changed_files` (blast-radius miscount). The
    `*` pattern also ignores this .gitignore itself, and `reset_hard_master`'s `git clean -fd` (no -x)
    preserves ignored files, so it survives across attempts."""
    fl = wt / ".fl"
    fl.mkdir(parents=True, exist_ok=True)
    (fl / ".gitignore").write_text("*\n", encoding="utf-8")


def checkout_master(wt: Path) -> None:
    # Detached HEAD at master's commit — NOT the master branch. In a linked worktree the master branch
    # is held by the main checkout (`git checkout master` fails with "already used by worktree"), and
    # committing on it would move the shared `master` ref. Detached HEAD lets us commit a fix onto a
    # branch without ever touching master.
    _git(wt, "checkout", "-f", "--detach", "master")


def reset_hard(wt: Path, ref: str) -> None:
    _git(wt, "reset", "--hard", ref)
    _git(wt, "clean", "-fd")


def reset_hard_master(wt: Path) -> None:
    reset_hard(wt, "master")


def changed_files(wt: Path) -> list[str]:
    out = _git(wt, "status", "--porcelain")
    files = []
    for line in out.splitlines():
        name = line[3:].strip()
        if name and not _is_artifact(name):
            files.append(name)
    return files


def commit_and_branch(wt: Path, message: str, branch: str) -> str:
    """Commit the working-tree edits on the current DETACHED HEAD (call `checkout_master` first), point
    `branch` at the commit, and return its sha. Because HEAD is detached, `git commit` never moves the
    shared `master` ref — the fix lands on an independent branch off master with no reset window."""
    _stage_non_artifacts(wt)
    _git(wt, "commit", "-m", message)
    sha = _git(wt, "rev-parse", "HEAD").strip()
    _git(wt, "branch", "-f", branch, sha)
    return sha


def commit_wip(wt: Path, message: str) -> str:
    """Stage all non-ignored changes and commit on the current DETACHED HEAD (call `checkout_master`
    first). Returns the new sha. Unlike `commit_and_branch` it does NOT create a branch — used for the
    intermediate 'regression test' commit that a rich-bug fix is layered on top of, so a failed fix can
    `reset_hard(wt, test_sha)` back to the proven test."""
    _stage_non_artifacts(wt)
    _git(wt, "commit", "-m", message)
    return _git(wt, "rev-parse", "HEAD").strip()


def suite_is_clean(wt: Path) -> bool:
    return not changed_files(wt)
