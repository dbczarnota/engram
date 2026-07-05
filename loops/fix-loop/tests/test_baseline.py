from __future__ import annotations

import baseline


class _Cfg:
    def __init__(self, verify):
        self.verify = verify


def test_run_verify_detailed_one_result_per_command():
    calls = []

    def fake_run(command, worktree):
        calls.append(command)
        return (0, "ok") if "ruff" not in command else (1, "E001 boom")

    cfg = _Cfg({"test": "pytest -q", "lint": "ruff check ."})
    results = baseline.run_verify_detailed(cfg, "/wt", run=fake_run)
    assert [r.name for r in results] == ["test", "lint"]
    assert results[0].exit_code == 0 and results[1].exit_code == 1
    assert results[1].command == "ruff check ." and "boom" in results[1].output


def test_run_verify_detailed_empty_when_no_verify():
    assert baseline.run_verify_detailed(_Cfg({}), "/wt", run=lambda c, w: (0, "")) == []


class _CfgS:
    def __init__(self, setup):
        self.setup = setup


def test_run_setup_all_pass():
    import baseline
    ok, detail = baseline.run_setup(_CfgS({"deps": "uv sync", "extra": "echo hi"}),
                                    "/wt", run=lambda c, w: (0, "ok"))
    assert ok is True


def test_run_setup_first_failure_aborts():
    import baseline
    calls = []

    def run(cmd, w):
        calls.append(cmd)
        return (1, "boom") if "sync" in cmd else (0, "ok")

    ok, detail = baseline.run_setup(_CfgS({"deps": "uv sync", "extra": "echo hi"}), "/wt", run=run)
    assert ok is False and "uv sync" in detail and "boom" in detail
    assert calls == ["uv sync"]        # aborts on first failure, does not run later commands


def test_run_setup_empty_is_ok():
    import baseline
    assert baseline.run_setup(_CfgS({}), "/wt", run=lambda c, w: (1, "x"))[0] is True


def test_resolve_verify_strong_path_with_docker():
    import baseline
    v = {"lint": "ruff check .",
         "test": {"requires": "docker", "with": "uv run pytest",
                  "without": "uv run pytest -m 'not requires_docker'"}}
    assert baseline.resolve_verify(v, docker_available=True) == {
        "lint": "ruff check .", "test": "uv run pytest"}


def test_resolve_verify_light_path_without_docker():
    import baseline
    v = {"test": {"requires": "docker", "with": "A", "without": "B"}}
    assert baseline.resolve_verify(v, docker_available=False) == {"test": "B"}


def test_resolve_verify_plain_strings_passthrough():
    import baseline
    assert baseline.resolve_verify({"lint": "ruff"}, docker_available=False) == {"lint": "ruff"}


def test_docker_available_false_when_cli_missing(monkeypatch):
    import baseline

    def _boom(*a, **k):
        raise OSError("no docker")

    monkeypatch.setattr(baseline.subprocess, "run", _boom)
    assert baseline.docker_available() is False
