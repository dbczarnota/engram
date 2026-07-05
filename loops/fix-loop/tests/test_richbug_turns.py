from __future__ import annotations

import json

import richbug
from report import Finding


class _P:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)
        self.stderr = ""


def _finding():
    return Finding(fingerprint="b:1", file="a.py", line=1, dimension="bug-hunt",
                   severity="high", layer="backend", summary="off-by-one")


def _plan():
    return {"root_cause": "rc", "approach": "ap", "alternatives": "alt", "justification": "why"}


def test_is_test_file():
    assert richbug._is_test_file("tests/test_x.py")
    assert richbug._is_test_file("pkg/test_x.py")
    assert richbug._is_test_file("pkg/x_test.py")
    assert richbug._is_test_file("a\\tests\\test_x.py")
    assert not richbug._is_test_file("pkg/a.py")
    assert not richbug._is_test_file("src/service.py")


def test_run_test_turn_ok_and_can_edit(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(richbug.rich, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": _plan()})

    monkeypatch.setattr(richbug.rich.subprocess, "run", _run)
    plan, tokens, status = richbug.run_test_turn(_finding(), tmp_path)
    assert status == "ok" and plan["justification"] == "why"
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob,Edit,Write"   # writes the test
    assert cmd[cmd.index("--disallowedTools") + 1] == "Bash"


def test_run_bug_impl_applied_and_feedback(monkeypatch, tmp_path):
    monkeypatch.setattr(richbug.rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(richbug.rich.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": False, "structured_output": {"applied": True, "self_critique": "ok"}}))
    status, critique, _tok = richbug.run_bug_impl(_finding(), _plan(), tmp_path, feedback="gate: suite RED foo")
    assert status == "applied" and critique == "ok"
    written = (tmp_path / ".fl" / "bugimpl.md").read_text(encoding="utf-8")
    assert "gate: suite RED foo" in written


def test_bug_skeptic_fail_open_on_error(monkeypatch, tmp_path):
    monkeypatch.setattr(richbug.rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(richbug.rich.subprocess, "run", lambda cmd, **k: _P(
        {"is_error": True, "api_error_status": 500, "result": "boom"}))
    verdict, _reason, _tok = richbug._bug_skeptic(_finding(), _plan(), tmp_path)
    assert verdict == "confirmed"        # never wrongly reject on skeptic failure


def test_bug_skeptic_is_read_only(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(richbug.rich, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": {"verdict": "confirmed", "reason": "ok"}})

    monkeypatch.setattr(richbug.rich.subprocess, "run", _run)
    richbug._bug_skeptic(_finding(), _plan(), tmp_path)
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob"
    assert "Edit,Write,Bash" in cmd[cmd.index("--disallowedTools") + 1]
