from __future__ import annotations

import subprocess
from pathlib import Path

import gitops
from gitops import changed_files, checkout_master, commit_and_branch, reset_hard_master


def _git(wt, *args):
    subprocess.run(["git", *args], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path) -> Path:
    wt = tmp_path / "r"
    wt.mkdir()
    _git(wt, "init", "-b", "master")
    _git(wt, "config", "user.email", "t@t")
    _git(wt, "config", "user.name", "t")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-m", "init")
    return wt


def test_changed_files_lists_edits(tmp_path):
    wt = _repo(tmp_path)
    (wt / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert changed_files(wt) == ["a.py"]


def test_commit_and_branch_creates_branch_off_master(tmp_path):
    wt = _repo(tmp_path)
    checkout_master(wt)                                     # detach at master, like the runner
    (wt / "a.py").write_text("x = 2\n", encoding="utf-8")
    sha = commit_and_branch(wt, "fix: bump", "fix/a")
    assert sha
    # the branch points at the new commit; master is unchanged
    branch_sha = subprocess.run(["git", "rev-parse", "fix/a"], cwd=wt, capture_output=True,
                                text=True).stdout.strip()
    assert branch_sha == sha
    master_content = subprocess.run(["git", "show", "master:a.py"], cwd=wt, capture_output=True,
                                    text=True).stdout
    assert "x = 1" in master_content            # master NOT moved


def test_reset_hard_master_discards(tmp_path):
    wt = _repo(tmp_path)
    (wt / "a.py").write_text("x = 999\n", encoding="utf-8")
    reset_hard_master(wt)
    assert (wt / "a.py").read_text(encoding="utf-8") == "x = 1\n"
    assert changed_files(wt) == []


def test_detached_ops_work_in_linked_worktree_master_held_by_main(tmp_path):
    # C1/C2 guard: in a real linked worktree, master is held by the main checkout. checkout_master must
    # NOT fail ("already used by worktree"), and commit_and_branch must not move the shared master ref.
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-b", "master")
    _git(main, "config", "user.email", "t@t")
    _git(main, "config", "user.name", "t")
    (main / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(main, "add", "-A")
    _git(main, "commit", "-m", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "--detach", str(wt), "master")

    checkout_master(wt)                                    # must not raise (master held by main)
    (wt / "a.py").write_text("x = 42\n", encoding="utf-8")
    sha = commit_and_branch(wt, "fix: bump", "fix/z")
    assert sha
    # the shared master ref is unchanged (the fix lives only on fix/z)
    master_content = subprocess.run(["git", "show", "master:a.py"], cwd=main,
                                    capture_output=True, text=True).stdout
    assert "x = 1" in master_content


def test_commit_wip_commits_on_detached_head_without_moving_master(tmp_path):
    wt = _repo(tmp_path)
    gitops.checkout_master(wt)                       # detached at master
    (wt / "t_new.py").write_text("assert True\n", encoding="utf-8")
    sha = gitops.commit_wip(wt, "test: regression")
    assert sha
    # HEAD is the new commit; master ref did NOT move
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True).stdout.strip()
    master = subprocess.run(["git", "rev-parse", "master"], cwd=wt, capture_output=True, text=True).stdout.strip()
    assert head == sha and head != master
    # the committed file is present at HEAD
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "t_new.py" in tree


def test_reset_hard_to_ref_keeps_that_commit(tmp_path):
    wt = _repo(tmp_path)
    gitops.checkout_master(wt)
    (wt / "t_new.py").write_text("assert True\n", encoding="utf-8")
    test_sha = gitops.commit_wip(wt, "test: regression")
    (wt / "a.py").write_text("x = 999  # bad fix\n", encoding="utf-8")   # uncommitted fix
    gitops.reset_hard(wt, test_sha)                  # drop the fix, keep the test commit
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8")          # fix gone
    assert (wt / "t_new.py").exists()                                    # test still present (committed)


def test_reset_hard_master_still_works(tmp_path):
    wt = _repo(tmp_path)
    gitops.checkout_master(wt)
    (wt / "a.py").write_text("x = 2\n", encoding="utf-8")
    gitops.reset_hard_master(wt)
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8")


def test_changed_files_ignores_build_artifacts(tmp_path):
    wt = _repo(tmp_path)
    (wt / "a.py").write_text("x = 2\n", encoding="utf-8")          # real change
    (wt / "__pycache__").mkdir()
    (wt / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00\x01")
    (wt / ".pytest_cache").mkdir()
    (wt / ".pytest_cache" / "CACHEDIR.TAG").write_text("x", encoding="utf-8")
    (wt / "stray.pyc").write_bytes(b"\x00")
    assert changed_files(wt) == ["a.py"]                            # artifacts filtered out


def test_commit_and_branch_never_commits_artifacts(tmp_path):
    wt = _repo(tmp_path)
    checkout_master(wt)
    (wt / "a.py").write_text("x = 2  # fix\n", encoding="utf-8")
    (wt / "__pycache__").mkdir()
    (wt / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00\x01")
    sha = commit_and_branch(wt, "fix: x", "fix/x")
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "a.py" in tree
    assert "__pycache__" not in tree and ".pyc" not in tree


def test_commit_wip_never_commits_artifacts(tmp_path):
    wt = _repo(tmp_path)
    checkout_master(wt)
    (wt / "test_new.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (wt / "__pycache__").mkdir()
    (wt / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\x00")
    sha = gitops.commit_wip(wt, "test: regression")
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", sha], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "test_new.py" in tree and "__pycache__" not in tree


def test_wip_branch_deterministic_and_prefixed():
    a = gitops.wip_branch("backend/a.py:foo:x")
    assert a == gitops.wip_branch("backend/a.py:foo:x") and a.startswith("wip/")


def test_branch_exists(tmp_path):
    wt = _repo(tmp_path)
    assert gitops.branch_exists(wt, "master") is True
    assert gitops.branch_exists(wt, "wip/does-not-exist-0000") is False
