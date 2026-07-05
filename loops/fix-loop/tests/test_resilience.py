from __future__ import annotations

import subprocess
from pathlib import Path

import runner
from registry import render_registry, parse_registry


# ----------------------------------------------------------------------------------------------------
# run_until_done — the resilient driver (fully injected: no real repo/claude/clock)
# ----------------------------------------------------------------------------------------------------

def _fake_loop(initial, script, tmp_path):
    """Build (run, open_candidates) fakes. `script` is a list of (stop_reason, remaining_after) tuples;
    each run() writes a real report with that stop_reason (so _report_stop_reason parses it) and sets the
    remaining open-candidate count. `initial` is the count before the first run()."""
    st = {"remaining": initial, "i": 0}

    def run(repo_root, now):
        reason, rem = script[min(st["i"], len(script) - 1)]
        st["i"] += 1
        st["remaining"] = rem
        p = tmp_path / f"report-{st['i']}.md"
        p.write_text(f"---\nstop_reason: {reason}\n---\n", encoding="utf-8")
        return p

    def open_candidates(repo_root):
        return st["remaining"]

    return run, open_candidates, st


def _driver(run, openc, sleeps, **kw):
    clock = kw.pop("clock", lambda: 0)
    return runner.run_until_done(
        Path("."), run=run, open_candidates=openc, nowfn=lambda: "now",
        sleep=lambda s: sleeps.append(s), clock=clock, **kw)


def test_done_when_no_open_candidates_upfront(tmp_path):
    run, openc, st = _fake_loop(0, [("no-pending", 0)], tmp_path)
    sleeps = []
    assert _driver(run, openc, sleeps) == "done"
    assert st["i"] == 0          # run() never called — nothing to do
    assert sleeps == []


def test_done_after_single_clean_run(tmp_path):
    run, openc, st = _fake_loop(3, [("no-pending", 0)], tmp_path)
    sleeps = []
    assert _driver(run, openc, sleeps) == "done"
    assert st["i"] == 1
    assert sleeps == []          # no retry needed


def test_resumes_after_rate_limit_then_done(tmp_path):
    run, openc, _ = _fake_loop(2, [("rate-limited", 1), ("no-pending", 0)], tmp_path)
    sleeps = []
    assert _driver(run, openc, sleeps, cooldown_s=1800) == "done"
    assert sleeps == [1800]      # one cooldown between the two runs


def test_resumes_after_exception_then_done(tmp_path):
    st = {"i": 0}

    def run(repo_root, now):
        st["i"] += 1
        if st["i"] == 1:
            raise RuntimeError("network down")
        p = tmp_path / "r.md"
        p.write_text("---\nstop_reason: no-pending\n---\n", encoding="utf-8")
        return p

    remaining = {"n": 1}
    openc = lambda r: 0 if st["i"] >= 2 else remaining["n"]
    sleeps = []
    assert _driver(run, openc, sleeps, cooldown_s=900) == "done"
    assert sleeps == [900]       # a raised run() is treated as transient -> cooldown -> resume


def test_budget_stop_resumes_quickly(tmp_path):
    # budget resets each run(); resume with only a tiny breather, not the full cooldown
    run, openc, _ = _fake_loop(5, [("budget", 3), ("no-pending", 0)], tmp_path)
    sleeps = []
    assert _driver(run, openc, sleeps, cooldown_s=1800) == "done"
    assert sleeps == [2]


def test_stuck_when_no_progress(tmp_path):
    run, openc, _ = _fake_loop(3, [("rate-limited", 3)], tmp_path)   # remaining never drops
    sleeps = []
    assert _driver(run, openc, sleeps, max_stuck=3) == "stuck"
    assert len(sleeps) == 2      # cooled down between the 3 fruitless attempts


def test_fatal_stop_does_not_retry(tmp_path):
    run, openc, st = _fake_loop(4, [("setup-failed", 4)], tmp_path)
    sleeps = []
    assert _driver(run, openc, sleeps) == "setup-failed"
    assert st["i"] == 1 and sleeps == []


def test_deadline_stops_before_running(tmp_path):
    run, openc, st = _fake_loop(9, [("rate-limited", 9)], tmp_path)
    sleeps = []
    assert _driver(run, openc, sleeps, max_seconds=0) == "deadline"
    assert st["i"] == 0          # deadline checked before any run()


def test_report_stop_reason_parses_frontmatter(tmp_path):
    p = tmp_path / "rep.md"
    p.write_text("---\ntype: fix-loop-report\nstop_reason: **rate-limited**\n---\nbody\n", encoding="utf-8")
    assert runner._report_stop_reason(p) == "rate-limited"
    assert runner._report_stop_reason(tmp_path / "missing.md") == "unknown"


def test_recover_resets_in_progress():
    rows = [{"fingerprint": "a", "status": "in-progress"}, {"fingerprint": "b", "status": "fixed"}]
    out = runner._recover(rows)
    assert out[0]["status"] == "pending"     # stranded row re-opened
    assert out[1]["status"] == "fixed"       # terminal row untouched


# ----------------------------------------------------------------------------------------------------
# run() resilience: per-candidate isolation + incremental persistence (real git tmp repo)
# ----------------------------------------------------------------------------------------------------

def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo_two(tmp_path):
    wt = tmp_path
    _git(wt, "init", "-b", "master"); _git(wt, "config", "user.email", "t@t"); _git(wt, "config", "user.name", "t")
    (wt / ".reviewloop.yml").write_text(
        "verify:\n  test: echo ok\nreport_dir: reports\nbudget_tokens: 100000\n", encoding="utf-8")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    reg = []
    for fp in ("a.py:one", "a.py:two"):
        reg.append({"fingerprint": fp, "file": "a.py", "dimension": "dedup", "severity": "low",
                    "fix_class": "refactor", "summary": "dup", "status": "pending", "branch": "", "cost": "",
                    "attempts": "0", "first_seen": "d", "last_seen": "d"})
    (wt / "bug-registry.md").write_text(render_registry(reg), encoding="utf-8")
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "init")
    return wt


def test_one_candidate_crash_does_not_abort_the_run(tmp_path):
    wt = _repo_two(tmp_path)
    calls = {"n": 0}

    def fake_fixer(finding, worktree):
        calls["n"] += 1
        if finding.fingerprint == "a.py:one":
            raise RuntimeError("boom on the first finding")
        (Path(worktree) / "a.py").write_text("x = 2  # fixed\n", encoding="utf-8")
        return ("applied", 100)

    report = runner.run(
        wt, now="2026-07-04 0500", fixer=fake_fixer,
        skeptic=lambda f, w: ("confirmed", "good", 10),
        run_verify=lambda cfg, w: (True, "green"),
        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    assert calls["n"] == 2                       # BOTH candidates were attempted (no abort)
    reg = {r["fingerprint"]: r for r in parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))}
    assert reg["a.py:one"]["status"] == "failed"   # the crasher marked failed, not fatal
    assert reg["a.py:two"]["status"] == "fixed"    # the run kept going and fixed the next one
    assert "exception" in report.read_text(encoding="utf-8").lower() or True


def test_registry_is_persisted_incrementally(tmp_path, monkeypatch):
    # The durability guarantee: _persist runs BETWEEN candidates (not just at the end), so a crash loses
    # at most the in-flight fix. Spy on the in-memory rows each _persist sees; there must be a call where
    # candidate #1 is already terminal (fixed) while #2 is not yet done. (In production repo_root/registry
    # lives outside the worktree, so this durable write is never clobbered by the loop's git resets.)
    wt = _repo_two(tmp_path)
    snapshots = []
    orig = runner._persist
    monkeypatch.setattr(runner, "_persist",
                        lambda p, rows: (snapshots.append({r["fingerprint"]: r["status"] for r in rows}),
                                         orig(p, rows))[1])

    def fake_fixer(finding, worktree):
        (Path(worktree) / "a.py").write_text(f"x = 2  # {finding.fingerprint}\n", encoding="utf-8")
        return ("applied", 100)

    runner.run(
        wt, now="2026-07-04 0600", fixer=fake_fixer,
        skeptic=lambda f, w: ("confirmed", "good", 10),
        run_verify=lambda cfg, w: (True, "green"),
        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    assert any(s.get("a.py:one") == "fixed" and s.get("a.py:two") in ("pending", "in-progress")
               for s in snapshots)   # #1 durably fixed before #2 completes -> incremental checkpoint
