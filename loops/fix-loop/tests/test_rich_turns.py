from __future__ import annotations

import json

import rich
from report import Finding


class _P:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)
        self.stderr = ""


def _finding():
    return Finding(fingerprint="x:1", file="a.py", line=1, dimension="dedup",
                   severity="low", layer="backend", summary="dup block")


def _plan():
    return {"root_cause": "rc", "approach": "ap", "alternatives": "alt", "justification": "why"}


def test_run_plan_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(rich.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": False, "structured_output": _plan()}))
    plan, tokens, status = rich.run_plan(_finding(), tmp_path)
    assert status == "ok" and plan["justification"] == "why"


def test_run_plan_is_read_only(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": _plan()})

    monkeypatch.setattr(rich.subprocess, "run", _run)
    rich.run_plan(_finding(), tmp_path)
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob"
    assert "Edit,Write,Bash" in cmd[cmd.index("--disallowedTools") + 1]


def test_run_impl_applied_and_edit_tools(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": {"applied": True, "self_critique": "ok"}})

    monkeypatch.setattr(rich.subprocess, "run", _run)
    status, critique, tokens = rich.run_impl(_finding(), _plan(), tmp_path, feedback="fix the red test")
    assert status == "applied" and critique == "ok"
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob,Edit,Write"
    assert cmd[cmd.index("--disallowedTools") + 1] == "Bash"


def test_run_impl_feedback_in_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(rich.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": False, "structured_output": {"applied": True, "self_critique": "c"}}))
    rich.run_impl(_finding(), _plan(), tmp_path, feedback="VERIFY RED: test_x failed")
    written = (tmp_path / ".fl" / "impl.md").read_text(encoding="utf-8")
    assert "VERIFY RED: test_x failed" in written


def test_run_plan_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(rich.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": True, "api_error_status": 429, "result": "session limit"}))
    _plan_out, _tok, status = rich.run_plan(_finding(), tmp_path)
    assert status == "rate-limited"


def test_run_plan_empty_output_is_error(monkeypatch, tmp_path):
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(rich.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": False, "structured_output": {}}))
    plan, _tok, status = rich.run_plan(_finding(), tmp_path)
    assert status == "error" and plan == {}
