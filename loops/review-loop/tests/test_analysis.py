from __future__ import annotations

import json

from analysis import PARSERS, parse_eslint, parse_pyright, parse_ruff, parse_tsc


def test_parse_ruff_maps_findings():
    stdout = json.dumps([
        {"code": "F401", "message": "`os` imported but unused",
         "filename": "src/a.py", "location": {"row": 3, "column": 1}},
        {"code": "E711", "message": "comparison to None",
         "filename": "src/b.py", "location": {"row": 10, "column": 5}},
    ])
    out = parse_ruff(stdout)
    assert out == [
        "src/a.py:3 F401 `os` imported but unused",
        "src/b.py:10 E711 comparison to None",
    ]


def test_parse_ruff_empty():
    assert parse_ruff("[]") == []


def test_parse_pyright_maps_errors_and_warnings_skips_info():
    stdout = json.dumps({"generalDiagnostics": [
        {"file": "src/a.py", "severity": "error", "rule": "reportReturnType",
         "message": "bad return", "range": {"start": {"line": 4, "character": 2}}},
        {"file": "src/b.py", "severity": "warning", "rule": "reportUnusedVariable",
         "message": "unused x", "range": {"start": {"line": 0, "character": 0}}},
        {"file": "src/c.py", "severity": "information", "rule": None,
         "message": "note", "range": {"start": {"line": 1, "character": 0}}},
    ]})
    out = parse_pyright(stdout)
    # pyright lines are 0-based -> display 1-based; information is skipped
    assert out == [
        "src/a.py:5 error [reportReturnType] bad return",
        "src/b.py:1 warning [reportUnusedVariable] unused x",
    ]


def test_parsers_registry_keys():
    assert set(PARSERS) == {"ruff", "pyright", "eslint", "tsc"}


import shlex
import sys
from pathlib import Path

from analysis import run_analysis
from config import ReviewLoopConfig


def _cfg(analysis: dict[str, str]) -> ReviewLoopConfig:
    return ReviewLoopConfig(verify={}, report_dir="r", max_iter=1, budget_tokens=1, analysis=analysis)


def test_run_analysis_collects_findings(tmp_path):
    # a fake "ruff" that prints ruff-shaped JSON on stdout (exit 0)
    ruff_json = '[{"code":"F401","message":"unused","filename":"a.py","location":{"row":1,"column":1}}]'
    body = f"print({ruff_json!r})"
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(body)}"
    findings, errors = run_analysis(_cfg({"ruff": cmd}), tmp_path)
    assert findings == ["a.py:1 F401 unused"]
    assert errors == []


def test_run_analysis_nonzero_exit_still_parsed(tmp_path):
    # ruff exits 1 when it finds issues; stdout must still be parsed
    body = 'import json,sys; print("[]"); sys.exit(1)'
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(body)}"
    findings, errors = run_analysis(_cfg({"ruff": cmd}), tmp_path)
    assert findings == []
    assert errors == []


def test_run_analysis_bad_output_is_tool_error(tmp_path):
    body = "print('not json')"
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(body)}"
    findings, errors = run_analysis(_cfg({"ruff": cmd}), tmp_path)
    assert findings == []
    assert len(errors) == 1 and errors[0].startswith("ruff:")


def test_run_analysis_missing_binary_is_tool_error(tmp_path):
    findings, errors = run_analysis(_cfg({"pyright": "definitely-not-a-real-binary-xyz"}), tmp_path)
    assert findings == []
    assert len(errors) == 1 and errors[0].startswith("pyright:")


def test_parse_pyright_collapses_multiline_message():
    # pyright embeds a newline+indented detail tree in message — collapse to one line
    stdout = json.dumps({"generalDiagnostics": [
        {"file": "a.py", "severity": "error", "rule": "reportX",
         "message": "bad type\n    detail one\n    detail two",
         "range": {"start": {"line": 0, "character": 0}}},
    ]})
    assert parse_pyright(stdout) == ["a.py:1 error [reportX] bad type detail one detail two"]


def test_run_analysis_unexpected_json_shape_is_tool_error(tmp_path):
    # ruff parser expects a JSON list; a JSON object triggers AttributeError inside the
    # parser and must be caught (never crash the run).
    body = 'import json; print(json.dumps({"unexpected": 1}))'
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(body)}"
    findings, errors = run_analysis(_cfg({"ruff": cmd}), tmp_path)
    assert findings == []
    assert len(errors) == 1 and errors[0].startswith("ruff:")


def test_run_analysis_timeout_is_tool_error(tmp_path):
    import shlex
    body = "import time; time.sleep(30)"
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(body)}"
    # patch the module-level timeout down so the test is fast
    import analysis
    orig = analysis._TIMEOUT_S
    analysis._TIMEOUT_S = 1
    try:
        findings, errors = run_analysis(_cfg({"ruff": cmd}), tmp_path)
    finally:
        analysis._TIMEOUT_S = orig
    assert findings == []
    assert len(errors) == 1 and "timed out" in errors[0]


def test_parse_eslint_maps_errors_and_warnings():
    stdout = json.dumps([
        {"filePath": "web/a.ts", "messages": [
            {"ruleId": "no-unused-vars", "severity": 2, "message": "x is unused", "line": 3, "column": 1},
            {"ruleId": "eqeqeq", "severity": 1, "message": "use ===", "line": 9, "column": 5},
        ]},
        {"filePath": "web/b.ts", "messages": []},
    ])
    assert parse_eslint(stdout) == [
        "web/a.ts:3 error [no-unused-vars] x is unused",
        "web/a.ts:9 warning [eqeqeq] use ===",
    ]


def test_parse_eslint_registered():
    assert "eslint" in PARSERS


def test_parse_tsc_maps_diagnostics():
    stdout = (
        "src/a.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        "src/b.ts(3,1): warning TS6133: 'x' is declared but never used.\n"
        "Found 2 errors.\n"  # summary line, must be skipped
    )
    assert parse_tsc(stdout) == [
        "src/a.ts:12 error [TS2322] Type 'string' is not assignable to type 'number'.",
        "src/b.ts:3 warning [TS6133] 'x' is declared but never used.",
    ]


def test_parse_tsc_empty():
    assert parse_tsc("Found 0 errors.\n") == []


def test_parse_tsc_registered():
    assert "tsc" in PARSERS
