from __future__ import annotations

from pathlib import Path

from adversarial import verify_findings
from report import Finding


def _f(layer, dim, summary, fp=None):
    return Finding(fingerprint=fp or summary, file="a.py", line=1, dimension=dim,
                   severity="low", layer=layer, summary=summary)


def test_partitions_confirmed_and_refuted():
    findings = [_f("backend", "bug-hunt", "real null deref"), _f("backend", "perf", "bogus N+1")]

    def review(finding, worktree):
        return ("refuted", "loop is bounded, not N+1") if finding.dimension == "perf" else ("confirmed", "holds")

    survivors, refuted, _tok = verify_findings(Path("."), findings, review=review)
    assert survivors == [findings[0]]
    assert len(refuted) == 1
    assert refuted[0][0].layer == "backend" and refuted[0][0].dimension == "perf"
    assert refuted[0][0].summary == "bogus N+1"
    assert "N+1" in refuted[0][1]


def test_cap_leaves_extra_as_survivors():
    findings = [_f("b", "bug-hunt", f"f{i}") for i in range(25)]
    calls = []

    def review(finding, worktree):
        calls.append(finding)
        return ("refuted", "x")

    survivors, refuted, _tok = verify_findings(Path("."), findings, review=review, max_checks=20)
    assert len(calls) == 20                 # cost cap respected
    assert len(refuted) == 20
    assert len(survivors) == 5              # the 5 beyond the cap survive unverified


def test_skeptic_confirmed_keeps_finding():
    findings = [_f("b", "security", "maybe real")]
    survivors, refuted, _tok = verify_findings(Path("."), findings,
                                         review=lambda f, w: ("confirmed", "skeptic could not run"))
    assert survivors == findings
    assert refuted == []


import json
import adversarial


class _FakeProc:
    def __init__(self, payload):
        self.stdout = json.dumps(payload)
        self.stderr = ""


def test_run_skeptic_refuted_is_not_swallowed(monkeypatch, tmp_path):
    # regression: the skeptic schema is {verdict,reason} (no findings list) — a successful skeptic
    # must still be able to return refuted (classify_outcome's "ok" is findings-specific).
    monkeypatch.setattr(adversarial, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(adversarial.subprocess, "run", lambda *a, **k: _FakeProc(
        {"is_error": False, "structured_output": {"verdict": "refuted", "reason": "guard already exists"}}))
    verdict, reason, _tok = adversarial._run_skeptic(_f("backend", "perf", "bogus N+1"), tmp_path)
    assert verdict == "refuted"
    assert "guard already exists" in reason


def test_run_skeptic_api_error_confirms(monkeypatch, tmp_path):
    monkeypatch.setattr(adversarial, "_claude_exe", lambda: "claude")
    monkeypatch.setattr(adversarial.subprocess, "run", lambda *a, **k: _FakeProc(
        {"is_error": True, "api_error_status": 500, "result": "boom"}))
    verdict, reason, _tok = adversarial._run_skeptic(_f("b", "bug-hunt", "x"), tmp_path)
    assert verdict == "confirmed"


def test_verify_findings_raising_review_keeps_finding():
    def boom(finding, worktree):
        raise RuntimeError("skeptic blew up")

    finding = _f("b", "bug-hunt", "keep me")
    survivors, refuted, _tok = verify_findings(Path("."), [finding], review=boom)
    assert survivors == [finding]
    assert refuted == []


def test_verify_findings_preserves_order_across_parallel():
    findings = [_f("b", "d", f"f{i}") for i in range(6)]

    def review(finding, worktree):
        i = int(finding.summary[1:])
        return ("refuted", "r") if i % 2 else ("confirmed", "c")

    survivors, refuted, _tok = verify_findings(Path("."), findings, review=review, max_workers=4)
    assert [s.summary for s in survivors] == ["f0", "f2", "f4"]
    assert [r[0].summary for r in refuted] == ["f1", "f3", "f5"]


def test_run_skeptic_writes_unique_prompt_file(monkeypatch, tmp_path):
    # concurrent skeptics must not share one prompt file (race). Each call writes a unique one.
    captured = []
    monkeypatch.setattr(adversarial, "_claude_exe", lambda: "claude")

    def fake_run(cmd, **k):
        captured.append(cmd[2])  # the short "-p" instruction referencing the prompt file
        return _FakeProc({"is_error": False, "structured_output": {"verdict": "confirmed", "reason": "ok"}})

    monkeypatch.setattr(adversarial.subprocess, "run", fake_run)
    adversarial._run_skeptic(_f("b", "d", "claim A"), tmp_path)
    adversarial._run_skeptic(_f("b", "d", "claim B"), tmp_path)
    assert captured[0] != captured[1]
    assert len(list((tmp_path / ".rl").glob("skeptic-*.md"))) == 2


def test_verify_findings_sums_skeptic_tokens():
    findings = [_f("b", "d", "f1"), _f("b", "d", "f2")]

    def review(finding, worktree):
        return ("confirmed", "ok", 40)      # 3-tuple: verdict, reason, tokens

    survivors, refuted, tokens = verify_findings(Path("."), findings, review=review)
    assert tokens == 80                      # 40 + 40 summed


def test_verify_findings_tolerates_two_tuple_review():
    # a legacy/injected review returning (verdict, reason) → tokens counted as 0, no crash
    finding = _f("b", "d", "f")
    survivors, refuted, tokens = verify_findings(
        Path("."), [finding], review=lambda f, w: ("confirmed", "ok"))
    assert survivors == [finding]
    assert tokens == 0
