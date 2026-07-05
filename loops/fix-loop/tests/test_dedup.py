from __future__ import annotations

import subprocess
from pathlib import Path

import runner
from backlog import dedup_key
from registry import parse_registry, render_registry


def test_dedup_key_parses_file_symbol_dimension():
    row = {"fingerprint": "backend/x.py:foo:issue-one", "dimension": "perf"}
    assert dedup_key(row) == ("backend/x.py", "foo", "perf")


def test_dedup_key_none_for_static_or_malformed():
    assert dedup_key({"fingerprint": "static:C:\a\b.py:45 SIM1", "dimension": "static-analysis"}) is None
    assert dedup_key({"fingerprint": "no-colons", "dimension": "perf"}) is None


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo_two_siblings(tmp_path):
    wt = tmp_path
    _git(wt, "init", "-b", "master"); _git(wt, "config", "user.email", "t@t"); _git(wt, "config", "user.name", "t")
    (wt / ".reviewloop.yml").write_text(
        'verify:\n  check: python -c "pass"\nreport_dir: reports\nbudget_tokens: 100000\n', encoding="utf-8")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    reg = []
    for slug in ("issue-one", "issue-two"):
        reg.append({"fingerprint": f"a.py:foo:{slug}", "file": "a.py", "dimension": "perf",
                    "severity": "medium", "fix_class": "refactor", "summary": f"perf {slug}",
                    "status": "pending", "branch": "", "cost": "", "attempts": "0",
                    "first_seen": "d", "last_seen": "d"})
    (wt / "bug-registry.md").write_text(render_registry(reg), encoding="utf-8")
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "init")
    return wt


def test_runner_subsumes_sibling_and_makes_one_branch(tmp_path):
    wt = _repo_two_siblings(tmp_path)
    calls = []

    def fake_fixer(finding, worktree):
        calls.append(finding.fingerprint)
        (Path(worktree) / "a.py").write_text("x = 2  # batched\n", encoding="utf-8")
        return ("applied", 100)

    report = runner.run(
        wt, now="2026-07-03 1900", fixer=fake_fixer,
        skeptic=lambda f, w: ("confirmed", "ok", 0), run_verify=lambda cfg, w: (True, "green"),
        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    # only the FIRST sibling was fixed; the second was subsumed (fixer never called on it)
    assert calls == ["a.py:foo:issue-one"]
    text = report.read_text(encoding="utf-8")
    assert "fixed: 1" in text and "Subsumed" in text
    branches = subprocess.run(["git", "branch"], cwd=wt, capture_output=True, text=True).stdout
    assert branches.count("fix/") == 1                      # exactly one fix branch, not two
    reg = {r["fingerprint"]: r for r in parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))}
    assert reg["a.py:foo:issue-one"]["status"] == "fixed"
    assert reg["a.py:foo:issue-two"]["status"] == "subsumed"
