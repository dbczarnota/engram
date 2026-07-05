from __future__ import annotations

import run_coverage


class _Cfg:
    def __init__(self, coverage):
        self.coverage = coverage


COBERTURA = ('<?xml version="1.0"?><coverage><packages><package><classes>'
             '<class filename="backend/a.py"><lines><line number="5" hits="2"/></lines></class>'
             '</classes></package></packages></coverage>')


def test_collect_disabled_when_no_coverage_cmd(tmp_path):
    assert run_coverage.collect(_Cfg(""), tmp_path, run=lambda c, w: (0, "")) is None


def test_collect_parses_written_xml(tmp_path):
    (tmp_path / "coverage.xml").write_text(COBERTURA, encoding="utf-8")
    cov = run_coverage.collect(_Cfg("pytest --cov"), tmp_path, run=lambda c, w: (0, "ok"))
    assert cov == {"backend/a.py": {5: 2}}


def test_collect_failsafe_none_on_command_failure(tmp_path):
    (tmp_path / "coverage.xml").write_text(COBERTURA, encoding="utf-8")
    assert run_coverage.collect(_Cfg("pytest --cov"), tmp_path, run=lambda c, w: (1, "boom")) is None


def test_collect_failsafe_none_when_no_xml(tmp_path):
    assert run_coverage.collect(_Cfg("pytest --cov"), tmp_path, run=lambda c, w: (0, "ok")) is None


def test_collect_for_branch_opens_fresh_worktree_setups_and_collects(tmp_path):
    calls = []

    def fake_open(repo, name, ref=None):
        calls.append(("open", repo, name, ref))
        return tmp_path

    def fake_setup(cfg, wt):
        calls.append(("setup", wt))
        return (True, "ok")

    def fake_close(repo, wt):
        calls.append(("close", repo, wt))

    def fake_collect(cfg, wt):
        calls.append(("collect", wt))
        return {"backend/a.py": {5: 2}}

    cov = run_coverage.collect_for_branch(
        _Cfg("pytest --cov"), "repo", "integrate/prod-safe",
        open_bundle=fake_open, setup_bundle=fake_setup, close_bundle=fake_close, collect=fake_collect)

    assert cov == {"backend/a.py": {5: 2}}
    kinds = [c[0] for c in calls]
    assert kinds == ["open", "setup", "collect", "close"]
    assert calls[0][3] == "integrate/prod-safe"     # opened AT the bundle branch


def test_collect_for_branch_disabled_when_no_coverage_cmd(tmp_path):
    called = []
    cov = run_coverage.collect_for_branch(
        _Cfg(""), "repo", "integrate/prod-safe",
        open_bundle=lambda *a, **k: called.append("open"),
        setup_bundle=lambda *a, **k: called.append("setup"),
        close_bundle=lambda *a, **k: called.append("close"),
        collect=lambda *a, **k: called.append("collect"))
    assert cov is None
    assert called == []          # never opened a worktree when disabled


def test_collect_for_branch_closes_worktree_even_on_setup_failure(tmp_path):
    calls = []
    cov = run_coverage.collect_for_branch(
        _Cfg("pytest --cov"), "repo", "integrate/prod-safe",
        open_bundle=lambda repo, name, ref=None: tmp_path,
        setup_bundle=lambda cfg, wt: (False, "boom"),
        close_bundle=lambda repo, wt: calls.append("close"),
        collect=lambda cfg, wt: calls.append("collect"))
    assert cov is None
    assert calls == ["close"]    # closed even though setup failed; collect never called
