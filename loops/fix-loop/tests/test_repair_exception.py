from __future__ import annotations

import subprocess
from pathlib import Path

import repair
from triage import Failure


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("def f():\n    return 3\n", encoding="utf-8")
    (tmp_path / "test_a.py").write_text("from a import f\n\ndef test_f():\n    assert f() == 2\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    import gitops; gitops.ensure_scratch(tmp_path); gitops.checkout_master(tmp_path)
    return tmp_path


def _fail():
    return Failure(id="test_a.py::test_f", command="pytest", file="test_a.py", snippet="assert f() == 2")


def _vd_target_gone_when_test_expects_3(cfg, wt, **k):
    # the failure is present until the test asserts == 3 (i.e. the test is corrected)
    from baseline import CommandResult
    body = (Path(wt) / "test_a.py").read_text(encoding="utf-8")
    red = "== 3" not in body
    return [CommandResult("test", "pytest", 1 if red else 0,
                          "FAILED test_a.py::test_f - assert 3 == 2\n" if red else "1 passed\n")]


def test_code_fix_exhausted_then_test_is_wrong_yields_proposed_test(tmp_path):
    wt = _repo(tmp_path)
    baseline_ids = {"test_a.py::test_f"}

    # code impl can never fix it (the code is right); returns applied-but-target-still-fails -> needs-human
    def code_impl(finding, plan, worktree, feedback=""):
        (Path(worktree) / "a.py").write_text("def f():\n    return 3  # unchanged-ish\n", encoding="utf-8")
        return ("applied", "c", 10)

    def judge(failure, worktree):
        return ("test-wrong", "f() correctly returns 3; the test wrongly expects 2", 15)

    def test_fixer(failure, justification, worktree, feedback=""):
        (Path(worktree) / "test_a.py").write_text(
            "from a import f\n\ndef test_f():\n    assert f() == 3\n", encoding="utf-8")
        return ("applied", "now asserts 3", 20)

    outcome, cost, reason = repair.run_repair_with_exception(
        object(), wt, _fail(), baseline_ids, impl_agent=code_impl, judge=judge, test_fixer=test_fixer,
        run_verify_detailed=_vd_target_gone_when_test_expects_3, max_retries=1)
    assert outcome == "proposed-test"
    assert "test-is-wrong" in reason
    assert "== 3" in (wt / "test_a.py").read_text(encoding="utf-8")   # corrected test left for the runner


def test_test_ok_verdict_stays_needs_human(tmp_path):
    wt = _repo(tmp_path)

    def code_impl(finding, plan, worktree, feedback=""):
        return ("no-op", "", 5)     # code path immediately exhausts

    outcome, _c, _r = repair.run_repair_with_exception(
        object(), wt, _fail(), {"test_a.py::test_f"}, impl_agent=code_impl,
        judge=lambda f, w: ("test-ok", "code is buggy", 8),
        test_fixer=lambda *a, **k: ("applied", "", 0),
        run_verify_detailed=_vd_target_gone_when_test_expects_3, max_retries=1)
    assert outcome == "needs-human"
    assert (wt / "test_a.py").read_text(encoding="utf-8").count("== 2") == 1   # test untouched


def test_code_fix_wins_never_reaches_judge(tmp_path):
    wt = _repo(tmp_path)

    def vd(cfg, w, **k):
        from baseline import CommandResult
        red = "return 2" not in (Path(w) / "a.py").read_text(encoding="utf-8")
        return [CommandResult("test", "pytest", 1 if red else 0,
                              "FAILED test_a.py::test_f\n" if red else "1 passed\n")]

    def code_impl(finding, plan, worktree, feedback=""):
        (Path(worktree) / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        return ("applied", "fix code", 30)

    judged = {"called": False}
    outcome, _c, _r = repair.run_repair_with_exception(
        object(), wt, _fail(), {"test_a.py::test_f"}, impl_agent=code_impl,
        judge=lambda f, w: judged.__setitem__("called", True) or ("test-wrong", "x", 0),
        test_fixer=lambda *a, **k: ("applied", "", 0), run_verify_detailed=vd, max_retries=1)
    assert outcome == "fixed" and judged["called"] is False
