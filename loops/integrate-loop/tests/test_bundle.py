from __future__ import annotations

import subprocess
from pathlib import Path

import bundle


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("a = 0\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("b = 0\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    # two disjoint fixes + one that conflicts with fix/a
    for br, f, content in [("fix/a", "a.py", "a = 1\n"), ("fix/b", "b.py", "b = 1\n"),
                           ("fix/a2", "a.py", "a = 2\n")]:
        _git(tmp_path, "checkout", "-q", "master")
        _git(tmp_path, "checkout", "-q", "-b", br)
        (tmp_path / f).write_text(content, encoding="utf-8")
        _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-q", "-m", br)
    _git(tmp_path, "checkout", "-q", "master")
    return tmp_path


def test_bundle_merges_disjoint_and_flags_conflict(tmp_path):
    repo = _repo(tmp_path)
    wt = bundle.open_bundle(repo, "prod-safe")
    assert bundle.try_merge(wt, "fix/a") is True
    assert bundle.try_merge(wt, "fix/b") is True          # disjoint -> merges
    assert bundle.try_merge(wt, "fix/a2") is False        # conflicts with fix/a -> False, merge aborted
    sha = bundle.finalize(repo, wt, "integrate/prod-safe")
    assert sha
    # the bundle branch has both a=1 and b=1, not a2
    show_a = subprocess.run(["git", "show", "integrate/prod-safe:a.py"], cwd=repo,
                            capture_output=True, text=True).stdout
    show_b = subprocess.run(["git", "show", "integrate/prod-safe:b.py"], cwd=repo,
                            capture_output=True, text=True).stdout
    assert "a = 1" in show_a and "b = 1" in show_b
    bundle.close_bundle(repo, wt)


def test_revert_last_drops_a_merge(tmp_path):
    repo = _repo(tmp_path)
    wt = bundle.open_bundle(repo, "canary")
    bundle.try_merge(wt, "fix/a")
    pre = bundle.head_sha(wt)                              # last green state = a merged
    bundle.try_merge(wt, "fix/b")
    bundle.revert_last(wt, pre)                            # drop fix/b -> back to exactly `pre`
    assert "b = 0" in (wt / "b.py").read_text(encoding="utf-8")
    assert "a = 1" in (wt / "a.py").read_text(encoding="utf-8")
    bundle.close_bundle(repo, wt)


def test_revert_drops_ALL_of_a_multi_commit_fix(tmp_path):
    # the CRITICAL scenario: a 2-commit fix branch. HEAD~1 would leave the first commit behind;
    # reverting to the captured pre-merge sha drops the whole rejected fix.
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "master"); _git(repo, "checkout", "-q", "-b", "fix/multi")
    (repo / "a.py").write_text("a = 9  # c1\n", encoding="utf-8")
    _git(repo, "add", "-A"); _git(repo, "commit", "-q", "-m", "c1")
    (repo / "a.py").write_text("a = 9  # c1 c2\n", encoding="utf-8")
    _git(repo, "add", "-A"); _git(repo, "commit", "-q", "-m", "c2")
    _git(repo, "checkout", "-q", "master")

    wt = bundle.open_bundle(repo, "canary2")
    pre = bundle.head_sha(wt)                              # == master
    assert bundle.try_merge(wt, "fix/multi") is True
    bundle.revert_last(wt, pre)                            # reject the whole 2-commit fix
    assert "a = 0" in (wt / "a.py").read_text(encoding="utf-8")   # NO residue of c1/c2
    assert bundle.head_sha(wt) == pre
    bundle.close_bundle(repo, wt)


def test_finalize_returns_none_when_nothing_merged(tmp_path):
    repo = _repo(tmp_path)
    wt = bundle.open_bundle(repo, "empty")
    assert bundle.finalize(repo, wt, "integrate/empty") is None
    bundle.close_bundle(repo, wt)


def test_open_bundle_ref_opens_at_given_branch(tmp_path):
    repo = _repo(tmp_path)
    wt = bundle.open_bundle(repo, "at-fix-a", ref="fix/a")
    assert "a = 1" in (wt / "a.py").read_text(encoding="utf-8")   # fix/a's content, not master's
    bundle.close_bundle(repo, wt)
