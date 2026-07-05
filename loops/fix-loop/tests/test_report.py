from __future__ import annotations

from fix_report import render_fix_report


def test_report_lists_fixed_failed_deferred_and_budget():
    md = render_fix_report("hf", "2026-07-02 0300",
                           fixed=[{"fingerprint": "x:1", "dimension": "dedup", "summary": "extracted",
                                   "branch": "fix/x", "cost": "120"}],
                           failed=[{"fingerprint": "y:1", "dimension": "perf", "summary": "n+1",
                                    "reason": "verify RED"}],
                           deferred=[{"fingerprint": "z:1", "dimension": "dedup", "summary": "dup"}],
                           budget_spent=120, budget_total=400000, stop_reason="no-pending")
    assert "fixed: 1" in md and "failed: 1" in md and "deferred: 1" in md
    assert "fix/x" in md and "verify RED" in md
    assert "stop_reason: no-pending" in md


def test_report_has_baseline_repair_section():
    from fix_report import render_fix_report

    text = render_fix_report(
        "demo", "2026-07-03 0600", fixed=[], failed=[], deferred=[],
        budget_spent=90, budget_total=100000, stop_reason="baseline-repair",
        repaired=[{"id": "test_a.py::test_a", "branch": "fix/x-1", "cost": "90"}],
        repair_needs_human=[{"id": "b.py:1:1", "reason": "exhausted retries"}],
        blocked_env=["[test] environment/infra (exit 124): timed out"])
    assert "Baseline repair" in text
    assert "repaired: 1" in text
    assert "test_a.py::test_a" in text and "fix/x-1" in text
    assert "blocked-environment" in text.lower() or "environment" in text.lower()
    assert "b.py:1:1" in text


def test_report_tags_proposed_test_change_as_high_scrutiny():
    text = render_fix_report(
        "demo", "2026-07-03 0600", fixed=[], failed=[], deferred=[],
        budget_spent=90, budget_total=100000, stop_reason="baseline-repair",
        repaired=[], repair_needs_human=[
            {"id": "test_a.py::test_a", "reason": "test-is-wrong: asserted the wrong thing",
             "branch": "fix/test-a-1", "kind": "proposed-test-change"}],
        blocked_env=[])
    assert "high-scrutiny" in text.lower()
    assert "test_a.py::test_a" in text and "fix/test-a-1" in text
    assert "test-is-wrong" in text
