from __future__ import annotations

import io
import json

from config import ReviewLoopConfig
from logsweep import run_log_sweep, logfire_query


def _cfg(logfire=None):
    return ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1, logfire=logfire)


def test_run_log_sweep_off_when_no_logfire():
    assert run_log_sweep(_cfg(None)) == ([], [])


def test_run_log_sweep_skips_without_token(monkeypatch):
    monkeypatch.delenv("LOGFIRE_READ_TOKEN", raising=False)
    findings, errors = run_log_sweep(_cfg("proj"))
    assert findings == []
    assert any("LOGFIRE_READ_TOKEN" in e for e in errors)


def test_run_log_sweep_formats_and_dedups(monkeypatch):
    monkeypatch.setenv("LOGFIRE_READ_TOKEN", "tok")

    def fake_query(base, token, sql):
        return [
            {"created_at": "2026-07-02T10:00", "exception_type": "ValueError", "message": "boom"},
            {"created_at": "2026-07-02T10:00", "exception_type": "ValueError", "message": "boom"},
            {"created_at": "2026-07-02T11:00", "level": 17, "message": "bad  thing"},
        ]

    findings, errors = run_log_sweep(_cfg("proj"), query=fake_query)
    assert errors == []
    assert len(findings) == 2                       # duplicate collapsed
    assert any("ValueError: boom" in f for f in findings)


def test_run_log_sweep_query_error_is_recorded(monkeypatch):
    monkeypatch.setenv("LOGFIRE_READ_TOKEN", "tok")

    def boom(base, token, sql):
        raise RuntimeError("HTTP 500")

    findings, errors = run_log_sweep(_cfg("proj"), query=boom)
    assert findings == []
    assert any("HTTP 500" in e for e in errors)


def test_logfire_query_transposes_columnar(monkeypatch):
    import logsweep

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    payload = {"columns": [{"name": "message", "values": ["a", "b"]},
                           {"name": "level", "values": [17, 17]}]}

    def fake_urlopen(req, timeout=None):
        return _Resp(json.dumps(payload).encode())

    monkeypatch.setattr(logsweep.urllib.request, "urlopen", fake_urlopen)
    rows = logfire_query("https://x", "tok", "SELECT 1")
    assert rows == [{"message": "a", "level": 17}, {"message": "b", "level": 17}]
