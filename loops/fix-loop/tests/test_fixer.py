from __future__ import annotations

import json

import fixer


class _P:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)
        self.stderr = ""


def _finding():
    from report import Finding
    return Finding(fingerprint="x:1", file="a.py", line=1, dimension="dedup",
                   severity="low", layer="backend", summary="dup block")


def test_run_fixer_applied(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(fixer.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": False, "structured_output": {"applied": True, "summary": "extracted helper"}}))
    outcome, tokens = fixer.run_fixer(_finding(), tmp_path)
    assert outcome == "applied"


def test_run_fixer_no_op_when_applied_false(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(fixer.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": False, "structured_output": {"applied": False, "summary": "no safe fix"}}))
    outcome, _ = fixer.run_fixer(_finding(), tmp_path)
    assert outcome == "no-op"


def test_run_fixer_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(fixer.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": True, "api_error_status": 429, "result": "session limit"}))
    outcome, _ = fixer.run_fixer(_finding(), tmp_path)
    assert outcome == "rate-limited"


def test_fixer_allows_edit_tools(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(fixer, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": {"applied": True, "summary": "x"}})

    monkeypatch.setattr(fixer.subprocess, "run", _run)
    fixer.run_fixer(_finding(), tmp_path)
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob,Edit,Write"
    assert "Bash" not in cmd[cmd.index("--allowedTools") + 1]   # no shell for a refactor
