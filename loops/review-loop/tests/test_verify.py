from __future__ import annotations

import sys
from pathlib import Path

from config import ReviewLoopConfig
from verify import _run, run_verify


def _cfg(verify):
    return ReviewLoopConfig(verify=verify, report_dir="r", max_iter=1, budget_tokens=1)


def test_all_pass():
    calls = []

    def run(command, worktree):
        calls.append(command)
        return (0, "ok")

    passed, detail = run_verify(_cfg({"test": "pytest", "lint": "ruff check ."}), Path("."), run=run)
    assert passed is True
    assert len(calls) == 2


def test_one_failure_reports_which():
    def run(command, worktree):
        return (0, "") if command.startswith("pytest") else (1, "E501 line too long")

    passed, detail = run_verify(_cfg({"test": "pytest", "lint": "ruff check ."}), Path("."), run=run)
    assert passed is False
    assert "lint" in detail
    assert "ruff check ." in detail
    assert "E501" in detail


def test_no_verify_commands_is_pass():
    passed, detail = run_verify(_cfg({}), Path("."), run=lambda c, w: (0, ""))
    assert passed is True


def test_command_that_cannot_run_is_failure():
    def run(command, worktree):
        return (127, "command not found: pytest")

    passed, detail = run_verify(_cfg({"test": "pytest"}), Path("."), run=run)
    assert passed is False
    assert "not found" in detail


def test_empty_command_string_is_failure():
    # a misconfigured empty/None verify command must fail conservatively, not crash
    passed, detail = run_verify(_cfg({"lint": ""}), Path("."))
    assert passed is False
    assert "empty" in detail.lower()


def test_non_utf8_child_output_does_not_crash(tmp_path):
    # Regression: a child that emits a cp1252 byte (0xb9 = '¹'), invalid as UTF-8, must NOT crash the
    # runner. Strict utf-8 decoding raised UnicodeDecodeError in a reader thread and killed a whole
    # fix-loop run on candidate 1 (2026-07-03). errors="replace" turns the bad byte into U+FFFD instead.
    exe = sys.executable.replace("\\", "/")  # forward slashes survive shlex.split; Windows accepts them
    payload = "import sys; sys.stdout.buffer.write(bytes([0x6f, 0x6b, 0xb9, 0x64, 0x6f, 0x6e, 0x65]))"
    code, output = _run(f'{exe} -c "{payload}"', tmp_path)
    assert code == 0
    assert "�" in output  # decoded to the replacement char, not an exception
