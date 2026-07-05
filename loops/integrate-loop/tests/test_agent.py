from __future__ import annotations

import json

import agent


class _P:
    def __init__(self, payload):
        self.stdout = json.dumps(payload); self.stderr = ""


class _Sig:
    dimension_class = "mechanical"; files_changed = 1; lines_changed = 17; small = True; sensitive = False


def test_agent_read_only_and_parses(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(agent, "_claude_exe", lambda: "claude")

    def _run(cmd, **k):
        captured["cmd"] = cmd
        return _P({"is_error": False, "structured_output": {"tier": "canary", "rationale": "watch ingest"}})

    monkeypatch.setattr(agent.subprocess, "run", _run)
    tier, rationale, _tok = agent.assess("N+1", "perf", "canary", _Sig(), "fix/x", tmp_path,
                                         diff_text="+ added a line")
    assert tier == "canary" and rationale == "watch ingest"
    cmd = captured["cmd"]
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob"
    assert "Edit,Write,Bash" in cmd[cmd.index("--disallowedTools") + 1]
    assert "+ added a line" in (tmp_path / ".il" / "assess.md").read_text(encoding="utf-8")
    assert (tmp_path / ".il" / ".gitignore").read_text(encoding="utf-8") == "*\n"


def test_agent_failsafe_keeps_floor_on_error(monkeypatch, tmp_path):
    monkeypatch.setattr(agent, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(agent.subprocess, "run",
                        lambda cmd, **k: _P({"is_error": True, "api_error_status": 500, "result": "boom"}))
    tier, rationale, _tok = agent.assess("s", "dedup", "prod-safe", _Sig(), "fix/x", tmp_path)
    assert tier == "prod-safe"   # floor kept (runner clamps anyway); never invents a bolder tier
