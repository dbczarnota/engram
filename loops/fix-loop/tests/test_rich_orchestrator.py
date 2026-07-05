from __future__ import annotations

import subprocess
from pathlib import Path

import gitops
import rich


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
    return Finding(fingerprint="x:1", file="a.py", line=1, dimension="dedup",
                   severity="low", layer="backend", summary="dup")


def _plan_ok(finding, wt):
    return ({"root_cause": "rc", "approach": "ap", "justification": "why"}, 50, "ok")


def test_rich_refactor_fixed_leaves_edit_in_worktree(tmp_path):
    wt = _repo(tmp_path)

    def impl(finding, plan, worktree, feedback=""):
        (Path(worktree) / "a.py").write_text("x = 2  # refactored\n", encoding="utf-8")
        return ("applied", "looks good", 100)

    outcome, plan, cost, reason = rich.run_rich_refactor(
        cfg=object(), worktree=wt, finding=_finding(),
        run_verify=lambda cfg, w: (True, "green"),
        plan_agent=_plan_ok, impl_agent=impl, skeptic=lambda f, p, w: ("confirmed", "ok", 10))
    assert outcome == "fixed"
    assert cost == 160                                   # 50 plan + 100 impl + 10 skeptic
    assert "x = 2" in (wt / "a.py").read_text(encoding="utf-8")   # edit left for the runner


def test_rich_refactor_retries_then_needs_human(tmp_path):
    wt = _repo(tmp_path)
    feedbacks = []

    def impl(finding, plan, worktree, feedback=""):
        feedbacks.append(feedback)
        (Path(worktree) / "a.py").write_text("BROKEN\n", encoding="utf-8")
        return ("applied", "c", 10)

    outcome, plan, cost, reason = rich.run_rich_refactor(
        cfg=object(), worktree=wt, finding=_finding(),
        run_verify=lambda cfg, w: (False, "FAILED test_x"),      # gate always red
        plan_agent=_plan_ok, impl_agent=impl, skeptic=lambda f, p, w: ("confirmed", "ok", 0),
        max_retries=2)
    assert outcome == "needs-human"
    assert len(feedbacks) == 3                            # initial + 2 retries
    assert any("FAILED test_x" in fb for fb in feedbacks[1:])   # failure fed back
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8")  # reverted


def test_rich_refactor_no_plan_is_needs_human(tmp_path):
    wt = _repo(tmp_path)
    outcome, _plan, _cost, reason = rich.run_rich_refactor(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=lambda cfg, w: (True, "green"),
        plan_agent=lambda f, w: ({}, 5, "error"), impl_agent=lambda *a, **k: ("applied", "c", 0),
        skeptic=lambda f, p, w: ("confirmed", "ok", 0))
    assert outcome == "needs-human"


def test_rich_refactor_rate_limited(tmp_path):
    wt = _repo(tmp_path)
    outcome, _plan, _cost, _reason = rich.run_rich_refactor(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=lambda cfg, w: (True, "green"),
        plan_agent=lambda f, w: ({}, 5, "rate-limited"),
        impl_agent=lambda *a, **k: ("applied", "c", 0), skeptic=lambda f, p, w: ("confirmed", "ok", 0))
    assert outcome == "rate-limited"


def test_rich_refactor_needs_human_preserves_last_attempt_on_wip(tmp_path):
    import gitops
    wt = _repo(tmp_path)
    gitops.checkout_master(wt)

    def impl(finding, plan, worktree, feedback=""):
        (Path(wt) / "a.py").write_text("x = 1\nBROKEN\n", encoding="utf-8")
        return ("applied", "c", 10)

    outcome, _plan, _cost, _reason = rich.run_rich_refactor(
        cfg=object(), worktree=wt, finding=_finding(), run_verify=lambda cfg, w: (False, "RED"),
        plan_agent=_plan_ok, impl_agent=impl, skeptic=lambda f, p, w: ("confirmed", "ok", 0), max_retries=1)

    assert outcome == "needs-human"
    wip = gitops.wip_branch(_finding().fingerprint)
    assert gitops.branch_exists(wt, wip)                                   # attempt preserved
    show = subprocess.run(["git", "show", f"{wip}:a.py"], cwd=wt, capture_output=True, text=True).stdout
    assert "BROKEN" in show                                                # the actual rejected attempt
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8") and "BROKEN" not in (wt / "a.py").read_text(encoding="utf-8")
