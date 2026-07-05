from __future__ import annotations

import subprocess
from pathlib import Path

import richbug


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def _finding():
    from report import Finding
    return Finding(fingerprint="b:1", file="a.py", line=1, dimension="bug-hunt",
                   severity="high", layer="backend", summary="bug")


def _plan_ok(finding, wt):
    # Turn 1 writes ONLY a test file.
    (Path(wt) / "test_bug.py").write_text("def test_bug():\n    import a\n    assert a.fixed\n", encoding="utf-8")
    return ({"root_cause": "rc", "approach": "ap", "justification": "why"}, 40, "ok")


def _verify_fixed_when_marker(cfg, wt):
    # RED until the fix marker is present in a.py; then GREEN.
    return (("fixed = True" in (Path(wt) / "a.py").read_text(encoding="utf-8")), "suite")


def test_rich_bug_fixed_commits_test_leaves_fix(tmp_path):
    wt = _repo(tmp_path)

    def impl(finding, plan, worktree, feedback=""):
        (Path(worktree) / "a.py").write_text("x = 1\nfixed = True\n", encoding="utf-8")
        return ("applied", "ok", 100)

    outcome, plan, cost, reason = richbug.run_rich_bug(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=_verify_fixed_when_marker,
        test_agent=_plan_ok, impl_agent=impl, skeptic=lambda f, p, w: ("confirmed", "ok", 10))
    assert outcome == "fixed"
    assert cost == 150                                   # 40 test + 100 impl + 10 skeptic
    # the test is committed at HEAD; the fix is left uncommitted for the runner
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "test_bug.py" in tree
    assert "fixed = True" in (wt / "a.py").read_text(encoding="utf-8")            # fix in working tree
    assert gitops_status_has_uncommitted(wt)                                       # fix not yet committed


def gitops_status_has_uncommitted(wt):
    out = subprocess.run(["git", "status", "--porcelain"], cwd=wt, capture_output=True, text=True).stdout
    return bool(out.strip())


def test_rich_bug_test_not_reproducing_is_needs_human(tmp_path):
    wt = _repo(tmp_path)
    outcome, _p, _c, reason = richbug.run_rich_bug(
        cfg=object(), worktree=wt, finding=_finding(),
        run_verify=lambda cfg, w: (True, "green"),          # suite GREEN even with only the test => not RED
        test_agent=_plan_ok, impl_agent=lambda *a, **k: ("applied", "c", 0),
        skeptic=lambda f, p, w: ("confirmed", "ok", 0))
    assert outcome == "needs-human" and "reproduc" in reason.lower()
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8")
    assert not (wt / "test_bug.py").exists()                # test commit discarded (reset to master)


def test_rich_bug_turn1_touches_nontest_is_needs_human(tmp_path):
    wt = _repo(tmp_path)

    def bad_turn1(finding, wt):
        (Path(wt) / "a.py").write_text("x = 2\n", encoding="utf-8")   # NOT a test file
        return ({"root_cause": "rc", "approach": "ap", "justification": "why"}, 10, "ok")

    outcome, _p, _c, reason = richbug.run_rich_bug(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=lambda cfg, w: (False, "red"),
        test_agent=bad_turn1, impl_agent=lambda *a, **k: ("applied", "c", 0),
        skeptic=lambda f, p, w: ("confirmed", "ok", 0))
    assert outcome == "needs-human"
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8")


def test_rich_bug_gate_fail_retries_keep_test_then_needs_human(tmp_path):
    wt = _repo(tmp_path)
    seen_test_during_retry = []

    def impl(finding, plan, worktree, feedback=""):
        # record whether the committed test is still present at each impl attempt
        seen_test_during_retry.append((Path(worktree) / "test_bug.py").exists())
        (Path(worktree) / "a.py").write_text("x = 1\nfixed = True\n", encoding="utf-8")
        return ("applied", "c", 10)

    outcome, _p, _c, reason = richbug.run_rich_bug(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=_verify_fixed_when_marker,
        test_agent=_plan_ok, impl_agent=impl,
        skeptic=lambda f, p, w: ("refuted", "not convinced", 0),    # gate always fails at skeptic
        max_retries=2)
    assert outcome == "needs-human"
    assert len(seen_test_during_retry) == 3                 # initial + 2 retries
    assert all(seen_test_during_retry)                      # the proven test survived every retry
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8") and "fixed" not in (wt / "a.py").read_text(encoding="utf-8")
    assert not (wt / "test_bug.py").exists()                # finally reset to master


def test_rich_bug_fix_touching_test_is_rejected(tmp_path):
    wt = _repo(tmp_path)

    def impl(finding, plan, worktree, feedback=""):
        # tamper: weaken the committed regression test AND make a production edit that greens the suite
        (Path(worktree) / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
        (Path(worktree) / "a.py").write_text("x = 1\nfixed = True\n", encoding="utf-8")
        return ("applied", "c", 10)

    outcome, _p, _c, _reason = richbug.run_rich_bug(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=_verify_fixed_when_marker,
        test_agent=_plan_ok, impl_agent=impl, skeptic=lambda f, p, w: ("confirmed", "ok", 0), max_retries=2)
    assert outcome == "needs-human"          # a fix that tampered with the test must never land
    assert not (wt / "test_bug.py").exists() # finally reset to master


def test_rich_bug_rate_limited_on_test_turn(tmp_path):
    wt = _repo(tmp_path)
    outcome, _p, _c, _r = richbug.run_rich_bug(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=lambda cfg, w: (False, "red"),
        test_agent=lambda f, w: ({}, 5, "rate-limited"),
        impl_agent=lambda *a, **k: ("applied", "c", 0), skeptic=lambda f, p, w: ("confirmed", "ok", 0))
    assert outcome == "rate-limited"
