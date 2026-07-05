from __future__ import annotations

from report import Finding
from registry import parse_registry, render_registry, update_registry


def _f(fp, dim="dedup", sev="low", summary="s"):
    return Finding(fingerprint=fp, file="a.py", line=1, dimension=dim, severity=sev,
                   layer="backend", summary=summary)


def test_new_finding_becomes_pending():
    rows = update_registry([], [_f("x:1")], today="2026-07-02")
    assert len(rows) == 1
    r = rows[0]
    assert r["fingerprint"] == "x:1" and r["status"] == "pending"
    assert r["first_seen"] == "2026-07-02" and r["last_seen"] == "2026-07-02"


def test_fix_class_derived_from_dimension():
    rows = update_registry([], [_f("x:1", dim="dedup"), _f("y:1", dim="security"),
                                _f("z:1", dim="perf")], today="2026-07-02")
    by = {r["fingerprint"]: r["fix_class"] for r in rows}
    assert by["x:1"] == "refactor"      # dedup/dead-code/complexity/perf/static -> refactor
    assert by["z:1"] == "refactor"
    assert by["y:1"] == "bug"           # bug-hunt/security/consistency -> bug


def test_known_fingerprint_updates_last_seen_only():
    existing = [{"fingerprint": "x:1", "file": "a.py", "dimension": "dedup", "severity": "low",
                 "fix_class": "refactor", "summary": "s", "status": "pending", "branch": "",
                 "cost": "", "attempts": "0", "first_seen": "2026-07-01", "last_seen": "2026-07-01"}]
    rows = update_registry(existing, [_f("x:1")], today="2026-07-02")
    assert len(rows) == 1
    assert rows[0]["first_seen"] == "2026-07-01"       # unchanged
    assert rows[0]["last_seen"] == "2026-07-02"        # bumped
    assert rows[0]["status"] == "pending"              # unchanged


def _fixed_row(branch="fix/x"):
    return {"fingerprint": "x:1", "file": "a.py", "dimension": "dedup", "severity": "low",
            "fix_class": "refactor", "summary": "s", "status": "fixed", "branch": branch,
            "cost": "10", "attempts": "1", "first_seen": "2026-07-01", "last_seen": "2026-07-01"}


def test_fixed_reappearing_while_UNMERGED_stays_fixed():
    # the fix lives on fix/x off master; master still shows the bug until the human merges it, so
    # re-detection is expected and must NOT churn the row to 'regressed' (that would break the chain).
    rows = update_registry([_fixed_row()], [_f("x:1")], today="2026-07-02",
                           is_merged=lambda b: False)
    assert rows[0]["status"] == "fixed"
    assert rows[0]["last_seen"] == "2026-07-02"


def test_fixed_reappearing_after_MERGE_becomes_regressed():
    # the fix WAS merged into master and the bug is still detected -> a genuine regression.
    rows = update_registry([_fixed_row()], [_f("x:1")], today="2026-07-02",
                           is_merged=lambda b: b == "fix/x")
    assert rows[0]["status"] == "regressed"


def test_wontfix_is_left_alone():
    existing = [{"fingerprint": "x:1", "file": "a.py", "dimension": "dedup", "severity": "low",
                 "fix_class": "refactor", "summary": "s", "status": "wontfix", "branch": "",
                 "cost": "", "attempts": "0", "first_seen": "2026-07-01", "last_seen": "2026-07-01"}]
    rows = update_registry(existing, [_f("x:1")], today="2026-07-02")
    assert rows[0]["status"] == "wontfix"


def test_absent_finding_is_not_closed():
    existing = [{"fingerprint": "x:1", "file": "a.py", "dimension": "dedup", "severity": "low",
                 "fix_class": "refactor", "summary": "s", "status": "pending", "branch": "",
                 "cost": "", "attempts": "0", "first_seen": "2026-07-01", "last_seen": "2026-07-01"}]
    rows = update_registry(existing, [], today="2026-07-02")   # x:1 not re-reported
    assert len(rows) == 1 and rows[0]["status"] == "pending"   # NOT auto-closed


def test_render_then_parse_roundtrips():
    rows = update_registry([], [_f("x:1", summary="dup block | note")], today="2026-07-02")
    text = render_registry(rows)
    back = parse_registry(text)
    assert back[0]["fingerprint"] == "x:1"
    assert back[0]["status"] == "pending"
    assert "dup block" in back[0]["summary"]


def test_parse_old_row_without_misses_defaults_zero():
    # an existing 12-column registry (pre-reconciliation) must still parse, misses -> "0"
    text = (
        "| fingerprint | file | dimension | severity | fix_class | summary | status | branch | cost | attempts | first_seen | last_seen |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| x:1 | a.py | dedup | low | refactor | s | pending |  |  | 0 | d | d |\n"
    )
    rows = parse_registry(text)
    assert len(rows) == 1
    assert rows[0]["fingerprint"] == "x:1" and rows[0]["misses"] == "0"


def test_render_then_parse_roundtrips_misses():
    rows = [{"fingerprint": "x:1", "file": "a.py", "dimension": "dedup", "severity": "low",
             "fix_class": "refactor", "summary": "s", "status": "pending", "branch": "", "cost": "",
             "attempts": "0", "first_seen": "d", "last_seen": "d", "misses": "3"}]
    assert parse_registry(render_registry(rows))[0]["misses"] == "3"


def _row(fp="x:1", status="pending", misses="0", attempts="0", branch=""):
    return {"fingerprint": fp, "file": "a.py", "dimension": "dedup", "severity": "low",
            "fix_class": "refactor", "summary": "s", "status": status, "branch": branch,
            "cost": "", "attempts": attempts, "first_seen": "d", "last_seen": "d", "misses": misses}


def test_absent_once_is_grace_not_resolved():
    rows = update_registry([_row(status="pending", misses="0")], [], today="d2")
    assert rows[0]["status"] == "pending" and rows[0]["misses"] == "1"


def test_absent_twice_resolves():
    rows = update_registry([_row(status="pending", misses="1")], [], today="d2")
    assert rows[0]["status"] == "resolved" and rows[0]["misses"] == "2"


def test_detected_resets_misses_and_bumps_last_seen():
    rows = update_registry([_row(status="pending", misses="1")], [_f("x:1")], today="d2")
    assert rows[0]["misses"] == "0" and rows[0]["last_seen"] == "d2" and rows[0]["status"] == "pending"


def test_resolved_reopens_on_redetect():
    rows = update_registry([_row(status="resolved", misses="2")], [_f("x:1")], today="d2")
    assert rows[0]["status"] == "pending" and rows[0]["misses"] == "0"


def test_failed_requeues_to_pending_on_detect():
    rows = update_registry([_row(status="failed", attempts="1")], [_f("x:1")], today="d2")
    assert rows[0]["status"] == "pending"


def test_wontfix_never_auto_resolves():
    rows = update_registry([_row(status="wontfix", misses="1")], [], today="d2")
    assert rows[0]["status"] == "wontfix"


def test_fixed_absent_twice_resolves():
    rows = update_registry([_row(status="fixed", branch="fix/x", misses="1")], [], today="d2",
                           is_merged=lambda b: False)
    assert rows[0]["status"] == "resolved"


def test_incomplete_scan_does_not_count_absence():
    # A failed/partial scan (rate-limited, api-error, no-output...) reports empty findings for
    # reasons unrelated to the bugs being gone. It must not increment misses or resolve rows.
    existing = [_fixed_row(), _row(fp="p:1", status="pending", misses="1")]
    rows = update_registry(existing, [], today="d2", scan_complete=False, is_merged=lambda b: False)
    by = {r["fingerprint"]: r for r in rows}
    assert by["x:1"]["status"] == "fixed" and by["x:1"].get("misses", "0") == "0"    # unchanged
    assert by["p:1"]["status"] == "pending" and by["p:1"]["misses"] == "1"           # unchanged


def test_complete_scan_still_counts_absence_control():
    # Control: the SAME rows with scan_complete=True (the default) DO increment misses / resolve,
    # proving the flag above is what gates the absence branch.
    existing = [_fixed_row(), _row(fp="p:1", status="pending", misses="1")]
    rows = update_registry(existing, [], today="d2", scan_complete=True, is_merged=lambda b: False)
    by = {r["fingerprint"]: r for r in rows}
    assert by["x:1"]["status"] == "fixed" and by["x:1"]["misses"] == "1"            # incremented
    assert by["p:1"]["status"] == "resolved"                                        # misses 1->2, resolves
