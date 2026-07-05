from __future__ import annotations

import subprocess
from pathlib import Path

import runner
from registry import render_registry, parse_registry


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    wt = tmp_path
    _git(wt, "init", "-b", "master"); _git(wt, "config", "user.email", "t@t"); _git(wt, "config", "user.name", "t")
    (wt / ".reviewloop.yml").write_text("verify:\n  test: python -m pytest -q\nreport_dir: reports\nbudget_tokens: 100000\n", encoding="utf-8")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    (wt / "test_a.py").write_text("def test_a():\n    import a\n    assert a.ok\n", encoding="utf-8")
    (wt / "bug-registry.md").write_text(render_registry([]), encoding="utf-8")   # no registry findings
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "init")
    return wt


def test_runner_repairs_a_red_baseline_on_a_branch(tmp_path, monkeypatch):
    wt = _repo(tmp_path)
    from baseline import CommandResult

    def fake_vd(cfg, w, **k):
        red = "ok = True" not in (Path(w) / "a.py").read_text(encoding="utf-8")
        out = "FAILED test_a.py::test_a - AttributeError\n" if red else "1 passed\n"
        return [CommandResult("test", "pytest", 1 if red else 0, out)]

    def fake_repair(cfg, worktree, failure, baseline_ids, **k):
        (Path(worktree) / "a.py").write_text("x = 1\nok = True\n", encoding="utf-8")
        return ("fixed", 90, "gate passed")

    monkeypatch.setattr(runner.baseline, "run_verify_detailed", fake_vd)
    monkeypatch.setattr(runner, "_default_verify", lambda cfg, w: (False, "red"))   # legacy path unused now
    monkeypatch.setattr(runner, "run_repair_with_exception", fake_repair)

    report = runner.run(wt, now="2026-07-03 0600",
                        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)
    text = report.read_text(encoding="utf-8")
    assert "Baseline repair" in text and "repaired: 1" in text.lower().replace("repaired", "repaired")
    branches = subprocess.run(["git", "branch"], cwd=wt, capture_output=True, text=True).stdout
    assert "fix/" in branches
    assert "x = 1" in subprocess.run(["git", "show", "master:a.py"], cwd=wt, capture_output=True, text=True).stdout


def test_runner_blocked_environment_makes_no_changes(tmp_path, monkeypatch):
    wt = _repo(tmp_path)
    from baseline import CommandResult
    monkeypatch.setattr(runner.baseline, "run_verify_detailed",
                        lambda cfg, w, **k: [CommandResult("test", "pytest", 124, "timed out")])
    called = {"repair": False}
    monkeypatch.setattr(runner, "run_repair_with_exception",
                        lambda *a, **k: called.__setitem__("repair", True) or ("fixed", 0, ""))
    report = runner.run(wt, now="2026-07-03 0600",
                        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)
    assert called["repair"] is False
    assert "blocked-environment" in report.read_text(encoding="utf-8")


def test_runner_records_proposed_test_change_as_high_scrutiny(tmp_path, monkeypatch):
    wt = _repo(tmp_path)
    from baseline import CommandResult
    monkeypatch.setattr(runner.baseline, "run_verify_detailed",
                        lambda cfg, w, **k: [CommandResult("test", "pytest", 1, "FAILED test_a.py::test_a\n")]
                        if "ok = True" not in (Path(w) / "a.py").read_text(encoding="utf-8")
                        else [CommandResult("test", "pytest", 0, "1 passed\n")])

    def fake_exc(cfg, worktree, failure, baseline_ids, **k):
        (Path(worktree) / "test_a.py").write_text("def test_a():\n    assert True  # corrected\n", encoding="utf-8")
        return ("proposed-test", 120, "test-is-wrong: the test asserted the wrong thing")

    monkeypatch.setattr(runner, "run_repair_with_exception", fake_exc)
    report = runner.run(wt, now="2026-07-03 0600",
                        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)
    text = report.read_text(encoding="utf-8")
    assert "proposed test change" in text.lower() or "test-is-wrong" in text
    assert "high-scrutiny" in text.lower() or "review" in text.lower()
    # a branch was created for the human to review
    assert "fix/" in subprocess.run(["git", "branch"], cwd=wt, capture_output=True, text=True).stdout


def test_runner_setup_failure_does_no_work(tmp_path, monkeypatch):
    wt = _repo(tmp_path)
    # configure a setup command; make run_setup fail
    (wt / ".reviewloop.yml").write_text(
        "setup:\n  deps: uv sync\nverify:\n  test: python -m pytest -q\nreport_dir: reports\nbudget_tokens: 100000\n",
        encoding="utf-8")
    import subprocess as _sp
    _sp.run(["git", "add", "-A"], cwd=wt, check=True, capture_output=True)
    _sp.run(["git", "commit", "-m", "cfg"], cwd=wt, check=True, capture_output=True)

    import baseline
    monkeypatch.setattr(baseline, "run_setup", lambda cfg, w, **k: (False, "[deps] `uv sync` exit 1\nno network"))
    called = {"repair": False, "verify": False}
    monkeypatch.setattr(runner, "run_repair_with_exception",
                        lambda *a, **k: called.__setitem__("repair", True) or ("fixed", 0, ""))
    monkeypatch.setattr(runner.baseline, "run_verify_detailed",
                        lambda *a, **k: called.__setitem__("verify", True) or [])

    report = runner.run(wt, now="2026-07-03 0700",
                        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)
    text = report.read_text(encoding="utf-8")
    assert "setup-failed" in text
    assert called["repair"] is False and called["verify"] is False   # no verify, no repair on setup failure
