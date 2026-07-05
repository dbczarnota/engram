from __future__ import annotations

import triage
from baseline import CommandResult


def _r(name, cmd, code, output):
    return CommandResult(name=name, command=cmd, exit_code=code, output=output)


PYTEST_FAIL = """............F
=================================== FAILURES ===================================
______________________________ test_median_even _______________________________
    def test_median_even():
>       assert median([1, 2, 3, 4]) == 2.5
E       assert 3 == 2.5
=========================== short test summary info ============================
FAILED test_stats.py::test_median_even - assert 3 == 2.5
1 failed, 3 passed in 0.05s
"""

RUFF_FAIL = "backend/api/articles.py:45:17: SIM105 Use `contextlib.suppress(ValueError)`\n"
PYRIGHT_FAIL = ("agents/pipeline/runner.py:166:24 - error: \"facts\" is not a known attribute of \"None\" "
                "(reportOptionalMemberAccess)\n")


def test_pytest_failure_harvested():
    tr = triage.classify([_r("test", "pytest -q", 1, PYTEST_FAIL)])
    assert tr.blocked_env == []
    assert [f.id for f in tr.failures] == ["test_stats.py::test_median_even"]


def test_ruff_and_pyright_failures_harvested():
    tr = triage.classify([_r("lint", "ruff check .", 1, RUFF_FAIL),
                          _r("type", "pyright", 1, PYRIGHT_FAIL)])
    ids = {f.id for f in tr.failures}
    assert "backend/api/articles.py:45:17" in ids
    assert "agents/pipeline/runner.py:166:24" in ids
    assert tr.blocked_env == []


def test_env_timeout_and_missing_tool_are_blocked():
    tr = triage.classify([_r("test", "pytest", 124, "timed out after 600s"),
                          _r("lint", "ruff check .", 127, "command not found: ruff")])
    assert len(tr.blocked_env) == 2 and tr.failures == []


def test_collection_error_is_environment_not_a_bug():
    out = "ImportError while importing test module\nerrors during collection\ncollected 0 items\n"
    tr = triage.classify([_r("test", "pytest", 2, out)])
    assert tr.failures == [] and len(tr.blocked_env) == 1


def test_docker_down_is_environment():
    tr = triage.classify([_r("test", "pytest", 1, "testcontainers: cannot connect to the Docker daemon")])
    assert tr.failures == [] and len(tr.blocked_env) == 1


def test_unparseable_nonzero_is_blocked_not_guessed():
    tr = triage.classify([_r("build", "make", 2, "some opaque failure with no file lines")])
    assert tr.failures == [] and len(tr.blocked_env) == 1


def test_pre_flight_blocked_when_only_env():
    tr = triage.classify([_r("test", "pytest", 124, "timed out")])
    assert triage.is_pre_flight_blocked(tr) is True


def test_pre_flight_not_blocked_when_a_real_failure_exists():
    tr = triage.classify([_r("test", "pytest", 1, PYTEST_FAIL)])
    assert triage.is_pre_flight_blocked(tr) is False


REAL_PYRIGHT = (
    r'c:\Users\x\myrepo\agents\_base\resilient.py' + '\n'
    r'  c:\Users\x\myrepo\agents\_base\resilient.py:8:8 - error: Import "logfire" could not be resolved (reportMissingImports)' + '\n'
    r'  c:\Users\x\myrepo\agents\_base\resilient.py:9:6 - error: Import "pydantic_ai" could not be resolved (reportMissingImports)' + '\n'
    '2 errors, 0 warnings, 0 informations\n'
)

REAL_RUFF = "backend/api/articles.py:45:17: SIM105 Use `contextlib.suppress(ValueError)`\n"


def test_real_indented_pyright_windows_paths_are_harvested():
    tr = triage.classify([_r("typecheck", "pyright", 1, REAL_PYRIGHT)])
    ids = {f.id for f in tr.failures}
    # two indented error lines harvested; the bare file-header line (no :line:col) is NOT a false match
    assert len(tr.failures) == 2
    assert any(i.endswith("resilient.py:8:8") for i in ids)
    assert any(i.endswith("resilient.py:9:6") for i in ids)
    assert tr.blocked_env == [] and tr.env_commands == set()


def test_ruff_forward_slash_still_harvested():
    tr = triage.classify([_r("lint", "ruff check .", 1, REAL_RUFF)])
    assert [f.id for f in tr.failures] == ["backend/api/articles.py:45:17"]


def test_pytest_failed_not_confused_by_line_tool():
    tr = triage.classify([_r("test", "pytest", 1, "FAILED test_x.py::test_a - boom\n")])
    assert [f.id for f in tr.failures] == ["test_x.py::test_a"]
