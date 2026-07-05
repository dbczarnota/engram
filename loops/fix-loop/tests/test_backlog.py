from __future__ import annotations

from backlog import select_fixes, set_status


def _row(fp, fix_class="refactor", status="pending", severity="low", dimension="dedup", attempts="0"):
    return {"fingerprint": fp, "file": "a.py", "dimension": dimension, "severity": severity,
            "fix_class": fix_class, "summary": "s", "status": status, "branch": "", "cost": "",
            "attempts": attempts, "first_seen": "d", "last_seen": "d"}


def test_selects_only_pending_refactor():
    rows = [_row("a", fix_class="refactor", status="pending"),
            _row("b", fix_class="bug", status="pending"),          # bug-class excluded in Phase 2
            _row("c", fix_class="refactor", status="fixed"),       # not pending
            _row("d", fix_class="refactor", status="regressed")]   # regressed counts
    picked = [r["fingerprint"] for r in select_fixes(rows)]
    assert picked == ["a", "d"] or picked == ["d", "a"]   # order asserted separately
    assert "b" not in picked and "c" not in picked


def test_orders_by_severity_then_dimension():
    rows = [_row("lo", severity="low", dimension="perf"),
            _row("hi", severity="high", dimension="dedup"),
            _row("me", severity="medium", dimension="complexity")]
    assert [r["fingerprint"] for r in select_fixes(rows)] == ["hi", "me", "lo"]


def test_skips_exhausted_attempts():
    rows = [_row("x", attempts="3")]
    assert select_fixes(rows, max_attempts=3) == []


def test_set_status_updates_row_fields():
    rows = [_row("x", status="pending")]
    out = set_status(rows, "x", "fixed", branch="fix/x", cost="120", attempts="1")
    assert out[0]["status"] == "fixed" and out[0]["branch"] == "fix/x"
    assert out[0]["cost"] == "120" and out[0]["attempts"] == "1"
