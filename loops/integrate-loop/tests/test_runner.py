from __future__ import annotations

import subprocess
from pathlib import Path

import runner
from registry import render_registry


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    _git(tmp_path, "init", "-b", "master"); _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".reviewloop.yml").write_text("report_dir: reports\nmax_iter: 1\nbudget_tokens: 1\n", encoding="utf-8")
    reg = [
        {"fingerprint": "a.py:foo:dup", "file": "backend/a.py", "dimension": "dedup", "severity": "low",
         "fix_class": "refactor", "summary": "dup", "status": "fixed", "branch": "fix/a", "cost": "10",
         "attempts": "1", "first_seen": "d", "last_seen": "d"},
        {"fingerprint": "b.py:bar:sec", "file": "backend/b.py", "dimension": "bug-hunt", "severity": "high",
         "fix_class": "bug", "summary": "org filter", "status": "fixed", "branch": "fix/b", "cost": "20",
         "attempts": "1", "first_seen": "d", "last_seen": "d"},
        {"fingerprint": "c.py:baz:todo", "file": "backend/c.py", "dimension": "perf", "severity": "low",
         "fix_class": "refactor", "summary": "n+1", "status": "pending", "branch": "", "cost": "",
         "attempts": "0", "first_seen": "d", "last_seen": "d"},
    ]
    (tmp_path / "bug-registry.md").write_text(render_registry(reg), encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    return tmp_path


def test_runner_tiers_fixed_rows_only_and_clamps(tmp_path):
    wt = _repo(tmp_path)

    # inject: agent tries to PROMOTE the security fix to prod-safe -> must be clamped to needs-human
    def fake_assess(summary, dimension, floor, sig, branch, repo, *, diff_text=""):
        return ("prod-safe", "agent says fine", 5)

    def fake_diffstat(repo, branch, base="master"):
        return (["backend/a.py"], 12) if branch == "fix/a" else (["backend/b.py"], 6)

    def fake_branch_diff(repo, branch, base="master", **kw):
        return f"diff for {branch}"

    report_path = runner.run(wt, now="2026-07-03 2100", assess=fake_assess, diffstat=fake_diffstat,
                             branch_diff=fake_branch_diff)
    text = report_path.read_text(encoding="utf-8")
    # only the 2 fixed rows are tiered; the pending row is ignored
    assert "prod-safe: 1" in text          # dedup a.py -> mechanical+small -> prod-safe (agent didn't lower)
    assert "needs-human: 1" in text        # bug-hunt b.py -> sensitive floor; agent 'prod-safe' clamped
    assert "fix/a" in text and "fix/b" in text and "fix/c" not in text


def test_runner_forces_needs_human_when_diff_empty_or_fails(tmp_path):
    wt = _repo(tmp_path)

    def fake_assess(summary, dimension, floor, sig, branch, repo, *, diff_text=""):
        return ("prod-safe", "agent says fine", 5)

    def fake_diffstat_raises(repo, branch, base="master"):
        raise RuntimeError("git diff failed")

    def fake_branch_diff_raises(repo, branch, base="master", **kw):
        raise RuntimeError("git diff failed")

    report_path = runner.run(wt, now="2026-07-03 2100", assess=fake_assess,
                             diffstat=fake_diffstat_raises, branch_diff=fake_branch_diff_raises)
    text = report_path.read_text(encoding="utf-8")
    assert "needs-human: 2" in text
    assert "could not compute the fix diff" in text


def test_runner_consolidates_and_demotes_pulled(tmp_path, monkeypatch):
    import runner
    wt = _repo(tmp_path)   # reuse the Plan-A fixture (2 fixed rows fix/a dedup, fix/b bug-hunt)
    from consolidate import BundleResult

    def fake_assess(summary, dimension, floor, sig, branch, repo, *, diff_text=""):
        return ("prod-safe", "agent says fine", 5)

    def fake_diffstat(repo, branch, base="master"):
        return (["backend/a.py"], 10)

    def fake_branch_diff(repo, branch, base="master", **kw):
        return f"diff for {branch}"

    def fake_consolidate(repo, cfg, tier, fixes, **k):
        # prod-safe bundle: include fix/a; nothing pulled
        if tier == "prod-safe":
            return BundleResult(tier=tier, branch="integrate/prod-safe", included=list(fixes))
        return BundleResult(tier=tier, branch=None)

    monkeypatch.setattr(runner, "consolidate", fake_consolidate)
    report = runner.run(wt, now="2026-07-03 2200",
                        assess=fake_assess,
                        diffstat=fake_diffstat, branch_diff=fake_branch_diff)
    text = report.read_text(encoding="utf-8")
    assert "integrate/prod-safe" in text


def test_runner_demotes_uncovered_prod_safe_to_canary(tmp_path, monkeypatch):
    import runner
    wt = _repo(tmp_path)                       # fix/a is dedup -> prod-safe floor
    from consolidate import BundleResult

    monkeypatch.setattr(runner, "consolidate",
                        lambda repo, cfg, tier, fixes, **k:
                            BundleResult(tier=tier, branch="integrate/prod-safe", included=list(fixes))
                            if tier == "prod-safe" else BundleResult(tier=tier, branch=None))
    # coverage says a.py line changed but NOT covered
    monkeypatch.setattr(runner.run_coverage, "collect_for_branch",
                        lambda cfg, repo, branch, **k: {"backend/a.py": {5: 0}})
    monkeypatch.setattr(runner.gitmeta, "branch_diff", lambda repo, br, base="master", **kw:
                        "+++ b/backend/a.py\n@@ -4,0 +5,1 @@\n+y = 2\n")

    report = runner.run(wt, now="2026-07-03 2300",
                        assess=lambda *a, **k: ("prod-safe", "mech", 0),
                        diffstat=lambda repo, br, base="master", **kw: (["backend/a.py"], 4))
    text = report.read_text(encoding="utf-8")
    # fix/a was prod-safe by floor but its changed line is uncovered -> demoted to canary
    assert "changed lines not covered" in text
