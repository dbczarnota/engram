from __future__ import annotations

from claude_iterate import parse_result


def _env(findings, is_error=False, output_tokens=42):
    return {
        "type": "result",
        "is_error": is_error,
        "num_turns": 4,
        "usage": {"output_tokens": output_tokens},
        "structured_output": {"findings": findings},
    }


def test_parse_result_builds_findings():
    env = _env([
        {"fingerprint": "a.py:f:null", "file": "a.py", "line": 12, "dimension": "bug-hunt",
         "severity": "high", "summary": "null deref"},
        {"fingerprint": "b.py:g:dup", "file": "b.py", "line": 5, "dimension": "dedup",
         "severity": "low", "summary": "duplicated block"},
    ])
    res = parse_result(env, "", "backend")
    assert res.parsed is True
    assert [f.fingerprint for f in res.findings] == ["a.py:f:null", "b.py:g:dup"]
    assert res.findings[0].file == "a.py" and res.findings[0].line == 12
    assert res.findings[0].dimension == "bug-hunt" and res.findings[0].layer == "backend"
    assert res.findings[1].severity == "low"
    assert res.tokens == 42


def test_parse_result_empty_findings_is_clean_not_failed():
    res = parse_result(_env([]))
    assert res.parsed is True          # genuine clean pass
    assert res.fingerprints == set()


def test_parse_result_is_error_is_not_parsed():
    res = parse_result(_env([{"fingerprint": "x", "file": "x", "summary": "x"}], is_error=True))
    assert res.parsed is False


def test_parse_result_missing_structured_output_is_not_parsed():
    assert parse_result({"type": "result", "is_error": False, "result": "some prose"}).parsed is False


def test_parse_result_empty_envelope_is_not_parsed():
    # claude printed prose -> envelope failed to parse -> {}
    assert parse_result({}).parsed is False


from claude_iterate import classify_outcome, parse_result


def test_classify_rate_limited_429_session_cap():
    env = {"is_error": True, "api_error_status": 429,
           "result": "You've hit your session limit · resets 5:50pm (Europe/Warsaw)"}
    kind, detail = classify_outcome(env, "")
    assert kind == "rate-limited"
    assert "session limit" in detail


def test_classify_api_error_500():
    env = {"is_error": True, "api_error_status": 500, "result": "Internal error"}
    kind, detail = classify_outcome(env, "")
    assert kind == "api-error"
    assert "500" in detail


def test_classify_no_envelope():
    kind, detail = classify_outcome({}, "I could not find a request to act on.")
    assert kind == "no-envelope"
    assert detail


def test_classify_no_output_success_without_structured():
    env = {"is_error": False, "num_turns": 3}
    kind, _ = classify_outcome(env, "")
    assert kind == "no-output"


def test_classify_ok_with_findings():
    env = {"is_error": False, "structured_output": {"findings": []}}
    kind, detail = classify_outcome(env, "")
    assert kind == "ok"
    assert detail == ""


def test_parse_result_rate_limited_sets_fields():
    env = {"is_error": True, "api_error_status": 429, "result": "session limit resets 5pm"}
    res = parse_result(env)
    assert res.parsed is False
    assert res.failure_kind == "rate-limited"
    assert "session limit" in res.error_detail


from claude_iterate import _retry, _is_retryable
from report import IterationResult


def _res(kind):
    if kind == "ok":
        return IterationResult(parsed=True)
    return IterationResult(parsed=False, failure_kind=kind, error_detail=kind)


def test_classify_prose_session_cap_is_rate_limited_not_no_envelope():
    # A session cap printed as prose (no JSON envelope) must not be treated as a
    # retryable no-envelope blip.
    kind, detail = classify_outcome({}, "You've hit your session limit · resets 5:50pm")
    assert kind == "rate-limited"
    assert "session limit" in detail


def test_retry_transient_then_success_counts_attempts():
    seq = ["api-error", "ok"]
    calls = []

    def run_once(attempt):
        calls.append(attempt)
        return (_res(seq[attempt - 1]), f"log{attempt}")

    res = _retry(run_once, max_attempts=3, base_delay=0.0, sleep=lambda s: None)
    assert res.parsed is True
    assert calls == [1, 2]
    assert "log1" in res.raw and "log2" in res.raw


def test_retry_session_cap_does_not_retry():
    calls = []

    # a rate-limited result whose detail names a session cap is NOT retryable
    def run_once(attempt):
        calls.append(attempt)
        r = IterationResult(parsed=False, failure_kind="rate-limited",
                            error_detail="You've hit your session limit resets 5:50pm")
        return (r, "log")

    res = _retry(run_once, max_attempts=3, base_delay=0.0, sleep=lambda s: None)
    assert res.failure_kind == "rate-limited"
    assert calls == [1]


def test_is_retryable_transient_429():
    assert _is_retryable(IterationResult(parsed=False, failure_kind="rate-limited",
                                         error_detail="rate limited (HTTP 429)")) is True
    assert _is_retryable(IterationResult(parsed=False, failure_kind="no-output")) is False


def test_findings_schema_requires_dimension():
    from claude_iterate import FINDINGS_SCHEMA
    item = FINDINGS_SCHEMA["properties"]["findings"]["items"]
    assert "dimension" in item["properties"]
    assert item["properties"]["dimension"]["type"] == "string"
    assert "dimension" in item["required"]


def test_merge_layers_combines_and_records_partial_failure():
    from claude_iterate import _merge_layers
    from report import Finding, IterationResult
    be = IterationResult(fingerprints={"x"}, findings=[
        Finding(fingerprint="b1", file="a.py", line=1, dimension="bug-hunt",
                severity="low", layer="backend", summary="b1")],
                         tokens=100, parsed=True)
    fe = IterationResult(parsed=False, failure_kind="rate-limited", error_detail="session limit")
    merged = _merge_layers([("backend", be), ("frontend", fe)])
    assert merged.parsed is True                       # backend still good
    assert [f.summary for f in merged.findings] == ["b1"]
    assert merged.tokens == 100
    assert merged.layers_reviewed == ["backend"]
    assert any(layer == "frontend" for layer, _ in merged.layer_failures)


def test_merge_layers_all_failed_is_not_parsed():
    from claude_iterate import _merge_layers
    from report import IterationResult
    a = IterationResult(parsed=False, failure_kind="rate-limited", error_detail="cap")
    b = IterationResult(parsed=False, failure_kind="api-error", error_detail="HTTP 500")
    merged = _merge_layers([("backend", a), ("frontend", b)])
    assert merged.parsed is False
    assert merged.failure_kind == "rate-limited"       # first failure


def test_passes_monolith_one_per_layer():
    from claude_iterate import _passes
    from config import ReviewLoopConfig
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1,
                           backend=["backend/**"], frontend=["frontend/**"], fanout=False)
    passes = _passes(cfg)
    assert [(layer, paths) for layer, paths, _dims in passes] == [
        ("backend", ["backend/**"]), ("frontend", ["frontend/**"])]
    assert all(len(dims) == 7 for _l, _p, dims in passes)   # all dimensions per pass


def test_passes_fanout_one_per_layer_and_dimension():
    from claude_iterate import _passes, _PROMPT_DIMENSIONS
    from config import ReviewLoopConfig
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1,
                           backend=["backend/**"], frontend=["frontend/**"], fanout=True)
    passes = _passes(cfg)
    assert len(passes) == 2 * len(_PROMPT_DIMENSIONS)       # 2 layers x 7 dims
    assert all(len(dims) == 1 for _l, _p, dims in passes)   # one dimension per focused pass


def test_claude_iterate_monolith_runs_one_pass_per_layer():
    import claude_iterate
    from config import ReviewLoopConfig
    from report import Finding, IterationResult
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1,
                           backend=["backend/**"], frontend=["frontend/**"], fanout=False)
    calls = []

    def fake_runner(cfg, worktree, iteration, layer, paths, dims, **kw):
        calls.append((layer, tuple(d[0] for d in dims)))
        return IterationResult(fingerprints={layer}, parsed=True, findings=[
            Finding(fingerprint="x", file="a.py", line=1, dimension="bug-hunt",
                    severity="low", layer=layer, summary="x")])

    merged = claude_iterate.claude_iterate(cfg, None, 1, _layer_runner=fake_runner)
    assert len(calls) == 2                                  # one pass per layer
    assert all(len(dims) == 7 for _layer, dims in calls)
    assert merged.parsed is True
    assert len(merged.findings) == 2                        # merged across passes


def test_claude_iterate_fanout_runs_pass_per_layer_and_dimension():
    import claude_iterate
    from config import ReviewLoopConfig
    from report import IterationResult
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1,
                           backend=["backend/**"], frontend=["frontend/**"], fanout=True)
    calls = []

    def fake_runner(cfg, worktree, iteration, layer, paths, dims, **kw):
        calls.append((layer, dims[0][0]))
        return IterationResult(parsed=True)

    claude_iterate.claude_iterate(cfg, None, 1, _layer_runner=fake_runner)
    assert len(calls) == 2 * len(claude_iterate._PROMPT_DIMENSIONS)   # layer x dimension


def test_review_pass_is_read_only_no_accept_edits(monkeypatch, tmp_path):
    # Chinese Wall: the nested review pass must NOT get acceptEdits (auto-approves Edit/Write in
    # headless), must disallow Edit/Write/Bash, and allow only Read/Grep/Glob.
    import claude_iterate
    from config import ReviewLoopConfig

    captured = {}
    monkeypatch.setattr(claude_iterate, "_claude_exe", lambda: "claude")

    class _P:
        stdout = '{"is_error": false, "structured_output": {"findings": []}}'
        stderr = ""

    def _fake_run(cmd, **k):
        captured["cmd"] = cmd
        return _P()

    monkeypatch.setattr(claude_iterate.subprocess, "run", _fake_run)
    cfg = ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1)
    claude_iterate._iterate_layer(cfg, tmp_path, 1, "backend", ["b/**"], [("bug-hunt", "x")],
                                  max_attempts=1, base_delay=0.0, sleep=lambda s: None)
    cmd = captured["cmd"]
    assert "acceptEdits" not in cmd
    assert "--disallowedTools" in cmd and "Edit,Write,Bash" in cmd
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob"
