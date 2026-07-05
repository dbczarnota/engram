from __future__ import annotations

import subprocess
from pathlib import Path

import repair


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "test_a.py").write_text("def test_a():\n    import a\n    assert a.ok\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    import gitops; gitops.ensure_scratch(tmp_path)
    return tmp_path


def _fail(fid="test_a.py::test_a"):
    from triage import Failure
    return Failure(id=fid, command="pytest", file="test_a.py", snippet=fid)


def _verify_from_marker(marker="ok = True"):
    # RED (target present) until the marker is in a.py; then that failure is gone.
    def vd(cfg, wt, **k):
        from baseline import CommandResult
        red = marker not in (Path(wt) / "a.py").read_text(encoding="utf-8")
        out = "FAILED test_a.py::test_a - AttributeError\n" if red else "1 passed\n"
        return [CommandResult("test", "pytest", 1 if red else 0, out)]
    return vd


def test_repair_fixes_code_and_leaves_edit(tmp_path):
    wt = _repo(tmp_path)
    import gitops; gitops.checkout_master(wt)
    vd = _verify_from_marker()
    baseline_ids = repair.failure_set(object(), wt, run_verify_detailed=vd)
    assert baseline_ids == {"test_a.py::test_a"}

    def impl(finding, plan, worktree, feedback=""):
        (Path(worktree) / "a.py").write_text("x = 1\nok = True\n", encoding="utf-8")
        return ("applied", "fixes it", 80)

    outcome, cost, reason = repair.run_repair_fix(
        object(), wt, _fail(), baseline_ids, impl_agent=impl, run_verify_detailed=vd)
    assert outcome == "fixed" and cost == 80
    assert "ok = True" in (wt / "a.py").read_text(encoding="utf-8")   # edit left for caller


def test_repair_rejects_touching_the_test(tmp_path):
    wt = _repo(tmp_path)
    import gitops; gitops.checkout_master(wt)
    vd = _verify_from_marker()
    baseline_ids = repair.failure_set(object(), wt, run_verify_detailed=vd)

    def impl_touches_test(finding, plan, worktree, feedback=""):
        # cheats by editing the test to pass, plus a code no-op
        (Path(worktree) / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
        (Path(worktree) / "a.py").write_text("x = 1\nok = True\n", encoding="utf-8")
        return ("applied", "c", 10)

    outcome, _cost, _reason = repair.run_repair_fix(
        object(), wt, _fail(), baseline_ids, impl_agent=impl_touches_test, run_verify_detailed=vd,
        max_retries=1)
    assert outcome == "needs-human"                       # test edit rejected every attempt
    assert "assert a.ok" in (wt / "test_a.py").read_text(encoding="utf-8")   # test restored


def test_repair_rejects_fix_that_adds_a_new_failure(tmp_path):
    wt = _repo(tmp_path)
    import gitops; gitops.checkout_master(wt)

    def vd(cfg, w, **k):
        from baseline import CommandResult
        body = (Path(w) / "a.py").read_text(encoding="utf-8")
        fails = []
        if "ok = True" not in body:
            fails.append("FAILED test_a.py::test_a - AttributeError")
        if "BROKE" in body:
            fails.append("FAILED test_b.py::test_b - NEW")     # a NEW failure not in baseline
        code = 1 if fails else 0
        return [CommandResult("test", "pytest", code, "\n".join(fails) + "\n")]

    baseline_ids = repair.failure_set(object(), wt, run_verify_detailed=vd)

    def impl(finding, plan, worktree, feedback=""):
        (Path(worktree) / "a.py").write_text("x = 1\nok = True\nBROKE\n", encoding="utf-8")  # target gone, new fail
        return ("applied", "c", 10)

    outcome, _c, _r = repair.run_repair_fix(
        object(), wt, _fail(), baseline_ids, impl_agent=impl, run_verify_detailed=vd, max_retries=1)
    assert outcome == "needs-human"                       # monotonic gate rejects the regression
    assert "x = 1" == (wt / "a.py").read_text(encoding="utf-8").strip()   # reverted to master


def test_repair_rate_limited(tmp_path):
    wt = _repo(tmp_path)
    import gitops; gitops.checkout_master(wt)
    vd = _verify_from_marker()
    baseline_ids = repair.failure_set(object(), wt, run_verify_detailed=vd)
    outcome, _c, _r = repair.run_repair_fix(
        object(), wt, _fail(), baseline_ids,
        impl_agent=lambda *a, **k: ("rate-limited", "", 0), run_verify_detailed=vd)
    assert outcome == "rate-limited"
