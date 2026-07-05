from __future__ import annotations

import subprocess
from pathlib import Path

import gitops
import repair
import richbug
import triage
from baseline import CommandResult


def _r(name, cmd, code, output):
    return CommandResult(name=name, command=cmd, exit_code=code, output=output)


# --- triage: genuine FAILED lines are NOT masked by an env marker in the same output ---
def test_failed_lines_win_over_env_marker_in_output():
    out = ("FAILED test_x.py::test_a - assert 1 == 2\n"
           "some traceback mentioning ImportError and docker in passing\n")
    tr = triage.classify([_r("test", "pytest", 1, out)])
    assert [f.id for f in tr.failures] == ["test_x.py::test_a"]
    assert tr.env_commands == set() and tr.blocked_env == []


def test_failed_command_without_harvest_records_env_command():
    tr = triage.classify([_r("test", "pytest", 2, "errors during collection\ncollected 0 items\n")])
    assert tr.failures == [] and tr.env_commands == {"test"}


# --- repair_gate: a fix that breaks a runnable command (collection error) is REJECTED ---
def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    gitops.ensure_scratch(tmp_path); gitops.checkout_master(tmp_path)
    return tmp_path


def test_repair_gate_rejects_fix_that_breaks_collection(tmp_path):
    wt = _repo(tmp_path)
    # baseline: pytest has one genuine failure -> pytest is NOT an env command at baseline
    baseline_ids = {"test_a.py::test_a"}
    baseline_env = set()   # pytest ran (had failures) at baseline

    # after the "fix", the target is gone from failures BUT pytest now fails to collect (syntax/import
    # break) -> classified as env_commands -> the gate must reject, not read it as green.
    def vd_broken_collection(cfg, w):
        return [CommandResult("test", "pytest", 2,
                              "ImportError while importing test module\nerrors during collection\ncollected 0 items\n")]

    (wt / "a.py").write_text("x = 1\nimport nonexistent_module\n", encoding="utf-8")
    ok, reason = repair.repair_gate(object(), wt, "test_a.py::test_a", baseline_ids, ["a.py"],
                                    baseline_env_cmds=baseline_env, run_verify_detailed=vd_broken_collection)
    assert ok is False and "un-runnable" in reason


def test_repair_gate_accepts_clean_fix(tmp_path):
    wt = _repo(tmp_path)
    baseline_ids = {"test_a.py::test_a"}
    (wt / "a.py").write_text("x = 2\n", encoding="utf-8")
    ok, reason = repair.repair_gate(object(), wt, "test_a.py::test_a", baseline_ids, ["a.py"],
                                    baseline_env_cmds=set(),
                                    run_verify_detailed=lambda cfg, w: [CommandResult("test", "pytest", 0, "1 passed\n")])
    assert ok is True


# --- minors ---
def test_conftest_is_treated_as_a_test_file():
    assert richbug._is_test_file("conftest.py")
    assert richbug._is_test_file("backend/tests/conftest.py")
    assert not richbug._is_test_file("backend/app/service.py")


def test_coverage_files_are_artifacts():
    assert gitops._is_artifact(".coverage")
    assert gitops._is_artifact(".coverage.host.1234")
    assert not gitops._is_artifact("coverage_report.py")


def test_triage_harvests_error_ids_separately():
    out = "FAILED test_a.py::test_a - assert x\nERROR test_b.py::test_b - fixture boom\n"
    tr = triage.classify([_r("test", "pytest", 1, out)])
    assert [f.id for f in tr.failures] == ["test_a.py::test_a"]
    assert tr.errors == {"test_b.py::test_b"}
    assert tr.env_commands == set()   # command had a FAILED harvest, so not env


def test_repair_gate_rejects_fix_that_regresses_a_test_into_error(tmp_path):
    wt = _repo(tmp_path)
    # baseline: two FAILED (repair one at a time); baseline_ids folds in FAILED (no baseline errors here)
    baseline_ids = {"test_a.py::test_a", "test_c.py::test_c"}
    (wt / "a.py").write_text("x = 2\n", encoding="utf-8")

    # after the "fix": target test_a passes, test_c STILL failed (tolerated), but a previously-green
    # test_d regressed into ERROR -> pytest still has FAILED (test_c) so NOT env; the new ERROR must be
    # caught via the errors set folded into `now`.
    def vd(cfg, w):
        return [CommandResult("test", "pytest", 1,
                              "FAILED test_c.py::test_c - still failing\nERROR test_d.py::test_d - new fixture error\n")]

    ok, reason = repair.repair_gate(object(), wt, "test_a.py::test_a", baseline_ids, ["a.py"],
                                    run_verify_detailed=vd)
    assert ok is False and "test_d.py::test_d" in reason
