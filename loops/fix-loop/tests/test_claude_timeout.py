from __future__ import annotations

import subprocess

import fixer
import rich
from report import Finding


def _finding():
    return Finding(fingerprint="x:1", file="a.py", line=1, dimension="dedup",
                   severity="low", layer="backend", summary="s")


def _raise_timeout(*a, **k):
    raise subprocess.TimeoutExpired(cmd="claude", timeout=rich._CLAUDE_TIMEOUT_S)


def test_rich_run_claude_timeout_is_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(rich.subprocess, "run", _raise_timeout)
    so, tok, status = rich._run_claude(tmp_path, "x.md", rich.PLAN_SCHEMA, "Read,Grep,Glob", "Bash")
    assert status == "rate-limited" and so == {} and tok == 0


def test_rich_run_claude_passes_a_timeout(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(rich, "_claude_exe", lambda: "claude")

    class _P:
        stdout = '{"is_error": false, "structured_output": {"root_cause":"a","approach":"b","justification":"c"}}'
        stderr = ""

    def _run(cmd, **k):
        captured.update(k)
        return _P()

    monkeypatch.setattr(rich.subprocess, "run", _run)
    rich._run_claude(tmp_path, "x.md", rich.PLAN_SCHEMA, "Read,Grep,Glob", "Bash")
    assert captured.get("timeout") == rich._CLAUDE_TIMEOUT_S


def test_run_fixer_timeout_is_rate_limited(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(fixer.subprocess, "run", _raise_timeout)
    outcome, tok = fixer.run_fixer(_finding(), tmp_path)
    assert outcome == "rate-limited" and tok == 0


def test_skeptic_timeout_is_fail_open_confirmed(monkeypatch, tmp_path):
    monkeypatch.setattr(fixer, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(fixer.subprocess, "run", _raise_timeout)
    verdict, reason, tok = fixer.skeptic_check(_finding(), tmp_path)
    assert verdict == "confirmed" and "timed out" in reason
