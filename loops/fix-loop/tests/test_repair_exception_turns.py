from __future__ import annotations

import json

import repair
from triage import Failure


class _P:
    def __init__(self, payload):
        self.stdout = json.dumps(payload); self.stderr = ""


def _fail():
    return Failure(id="test_a.py::test_a", command="pytest", file="test_a.py", snippet="assert 3 == 2.5")


def test_judge_read_only_and_verdict(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(repair.rich, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": {"verdict": "test-wrong", "justification": "j"}})

    monkeypatch.setattr(repair.rich.subprocess, "run", _run)
    verdict, just, _tok = repair.judge_test_wrong(_fail(), tmp_path)
    assert verdict == "test-wrong" and just == "j"
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob"
    assert "Edit,Write,Bash" in cmd[cmd.index("--disallowedTools") + 1]


def test_judge_fails_closed_on_error(monkeypatch, tmp_path):
    monkeypatch.setattr(repair.rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(repair.rich.subprocess, "run",
                        lambda cmd, **k: _P({"is_error": True, "api_error_status": 500, "result": "boom"}))
    verdict, _j, _t = repair.judge_test_wrong(_fail(), tmp_path)
    assert verdict == "test-ok"          # fail-closed: never license a test change on an errored judge


def test_fix_test_can_edit_and_feedback(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(repair.rich, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": {"applied": True, "self_critique": "ok"}})

    monkeypatch.setattr(repair.rich.subprocess, "run", _run)
    status, crit, _t = repair.fix_test(_fail(), "because", tmp_path, feedback="gate: new failure")
    assert status == "applied" and crit == "ok"
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob,Edit,Write"
    written = (tmp_path / ".fl" / "testfix.md").read_text(encoding="utf-8")
    assert "gate: new failure" in written and "because" in written
