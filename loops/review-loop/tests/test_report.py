from __future__ import annotations

from report import Finding, IterationResult, render_report


def _f(layer, dim, summary, fp=None, sev="low"):
    return Finding(fingerprint=fp or summary, file="a.py", line=1, dimension=dim,
                   severity=sev, layer=layer, summary=summary)


def test_report_has_frontmatter_and_read_false():
    r = IterationResult(fingerprints={"a"}, findings=[
        _f("backend", "bug-hunt", "fix null guard"),
        _f("backend", "security", "risky change X"),
    ], tokens=1200)
    md = render_report("myrepo", "review-loop/2026-07-01-0300",
                       [r], "clean", "2026-07-01 03:00")
    assert md.startswith("---\n")
    assert "type: loop-report" in md
    assert "read: false" in md
    assert "branch: review-loop/2026-07-01-0300" in md
    assert "stop_reason: clean" in md
    assert "fix null guard" in md
    assert "risky change X" in md


def test_report_counts_totals():
    r1 = IterationResult(fingerprints={"a"}, findings=[_f("backend", "bug-hunt", "f1")], tokens=100)
    r2 = IterationResult(fingerprints={"b"}, findings=[_f("frontend", "security", "ro1")], tokens=200)
    md = render_report("repo", "b", [r1, r2], "max_iter", "2026-07-01 03:00")
    assert "findings: 2" in md


def test_report_renders_static_analysis_section():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())],
                       "clean", "2026-07-01 03:00",
                       analysis_findings=["a.py:1 F401 unused"], analysis_errors=[])
    assert "analysis_findings: 1" in md
    assert "## Static analysis" in md
    assert "a.py:1 F401 unused" in md


def _reg(fp, status):
    return {"fingerprint": fp, "file": "a.py", "dimension": "dedup", "severity": "low",
            "fix_class": "refactor", "summary": "sum " + fp, "status": status, "branch": "b",
            "cost": "", "attempts": "0", "first_seen": "d", "last_seen": "d", "misses": "0"}


def test_report_bucket_section_lists_open_and_resolved():
    rows = [_reg("a:1", "pending"), _reg("b:1", "needs-human"), _reg("c:1", "fixed"),
            _reg("d:1", "resolved"), _reg("e:1", "regressed")]
    out = render_report("repo", "rl/x", results=[], stop_reason="clean", started_at="now",
                        registry_rows=rows)
    assert "## Bucket" in out
    assert "pending 1" in out and "needs-human 1" in out and "resolved 1" in out
    # OPEN list shows the actionable ones, not resolved/fixed
    assert "a:1" in out and "b:1" in out and "e:1" in out


def test_report_static_analysis_tool_error_shown():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())],
                       "clean", "2026-07-01 03:00",
                       analysis_findings=[], analysis_errors=["pyright: could not run"])
    assert "## Static analysis" in md
    assert "pyright: could not run" in md


def test_report_no_analysis_section_when_absent():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())],
                       "clean", "2026-07-01 03:00")
    assert "## Static analysis" not in md
    assert "analysis_findings: 0" in md


def test_report_rate_limited_banner_and_detail():
    res = IterationResult(parsed=False, failure_kind="rate-limited",
                          error_detail="You've hit your session limit resets 5:50pm")
    md = render_report("demo", "rl/x", [res], "rate-limited", "2026-07-02 1200")
    assert "RATE-LIMITED" in md
    assert "resets 5:50pm" in md


def test_report_api_error_banner():
    res = IterationResult(parsed=False, failure_kind="api-error", error_detail="HTTP 500: boom")
    md = render_report("demo", "rl/x", [res], "api-error", "2026-07-02 1200")
    assert "API error" in md
    assert "HTTP 500" in md


def test_report_groups_report_only_by_layer_and_dimension():
    r = IterationResult(fingerprints={"a", "b"}, findings=[
        _f("backend", "security", "sql injection in query"),
        _f("frontend", "perf", "N+1 in loop"),
    ], parsed=True, layers_reviewed=["backend", "frontend"])
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00")
    assert "### backend" in md
    assert "### frontend" in md
    assert "#### security" in md
    assert "sql injection in query" in md


def test_report_lists_dimensions_reviewed_when_parsed():
    r = IterationResult(fingerprints=set(), parsed=True)
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00")
    assert "Dimensions reviewed" in md
    assert "log-sweep" in md


def test_report_omits_dimensions_line_when_not_reviewed():
    r = IterationResult(parsed=False, failure_kind="rate-limited", error_detail="session limit")
    md = render_report("repo", "b", [r], "rate-limited", "2026-07-02 12:00")
    assert "Dimensions reviewed" not in md


def test_report_shows_layer_failure():
    r = IterationResult(fingerprints={"a"}, findings=[_f("backend", "bug-hunt", "b1")],
                        parsed=True, layers_reviewed=["backend"],
                        layer_failures=[("frontend", "rate-limited: session limit resets 5pm")])
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00")
    assert "frontend" in md
    assert "rate-limited" in md


def test_report_lists_layers_reviewed():
    r = IterationResult(fingerprints=set(), parsed=True, layers_reviewed=["backend", "frontend"])
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00")
    assert "Layers reviewed" in md
    assert "backend" in md and "frontend" in md


def test_report_renders_log_errors_section():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())],
                       "clean", "2026-07-02 12:00",
                       log_findings=["2026-07-02T10:00 ValueError: boom"], log_errors=[])
    assert "log_findings: 1" in md
    assert "## Log errors (Logfire)" in md
    assert "ValueError: boom" in md


def test_report_log_sweep_note_shown():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())],
                       "clean", "2026-07-02 12:00",
                       log_findings=[], log_errors=["log-sweep skipped: no LOGFIRE_READ_TOKEN"])
    assert "## Log errors (Logfire)" in md
    assert "no LOGFIRE_READ_TOKEN" in md


def test_report_no_log_section_when_absent():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())], "clean", "2026-07-02 12:00")
    assert "## Log errors (Logfire)" not in md
    assert "log_findings: 0" in md


def test_report_renders_vault_todos_section():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())],
                       "clean", "2026-07-02 12:00",
                       todo_findings=["Fix the thing #deferred"], todo_errors=[])
    assert "vault_todos: 1" in md
    assert "## Vault TODOs" in md
    assert "Fix the thing" in md


def test_report_no_vault_todos_section_when_absent():
    md = render_report("repo", "b", [IterationResult(fingerprints=set())], "clean", "2026-07-02 12:00")
    assert "## Vault TODOs" not in md
    assert "vault_todos: 0" in md


def test_report_no_findings_says_none():
    r = IterationResult(fingerprints=set(), parsed=True)
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00")
    assert "- (none)" in md


def test_report_renders_refuted_section_and_count():
    kept = _f("backend", "bug-hunt", "kept one")
    r = IterationResult(fingerprints={"a"}, findings=[kept], parsed=True)
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00",
                       report_only_override=[kept],
                       refuted_findings=[(_f("backend", "perf", "bogus N+1"), "loop is bounded")])
    assert "refuted: 1" in md
    assert "## Filtered out" in md
    assert "bogus N+1" in md
    assert "loop is bounded" in md
    assert "kept one" in md            # survivor still shown


def test_report_override_replaces_report_only():
    r = IterationResult(fingerprints={"a"}, findings=[_f("backend", "bug-hunt", "original")], parsed=True)
    md = render_report("repo", "b", [r], "clean", "2026-07-02 12:00",
                       report_only_override=[])          # everything refuted
    assert "findings: 0" in md
    assert "original" not in md
    assert "refuted: 0" in md          # none passed => absent list defaults to 0
