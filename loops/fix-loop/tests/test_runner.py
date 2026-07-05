from __future__ import annotations

import subprocess
from pathlib import Path

import runner
from registry import render_registry, parse_registry


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    wt = tmp_path
    _git(wt, "init", "-b", "master"); _git(wt, "config", "user.email", "t@t"); _git(wt, "config", "user.name", "t")
    (wt / ".reviewloop.yml").write_text("verify:\n  test: echo ok\nreport_dir: reports\nbudget_tokens: 100000\n", encoding="utf-8")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    reg = [{"fingerprint": "x:1", "file": "a.py", "dimension": "dedup", "severity": "low",
            "fix_class": "refactor", "summary": "dup", "status": "pending", "branch": "", "cost": "",
            "attempts": "0", "first_seen": "d", "last_seen": "d"}]
    (wt / "bug-registry.md").write_text(render_registry(reg), encoding="utf-8")
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "init")
    return wt


def test_fix_loop_lands_a_refactor_on_a_branch(tmp_path, monkeypatch):
    wt = _repo(tmp_path)

    def fake_fixer(finding, worktree):
        (Path(worktree) / "a.py").write_text("x = 2  # refactored\n", encoding="utf-8")
        return ("applied", 100)

    report_path = runner.run(
        wt, now="2026-07-02 0300",
        fixer=fake_fixer,
        skeptic=lambda f, w: ("confirmed", "good", 10),
        run_verify=lambda cfg, w: (True, "green"),
        create_worktree=lambda root, br: root,
        remove_worktree=lambda root, wt: None)

    text = report_path.read_text(encoding="utf-8")
    assert "fixed: 1" in text and "fix/" in text
    # a fix branch exists off master; master unchanged
    branches = subprocess.run(["git", "branch"], cwd=wt, capture_output=True, text=True).stdout
    assert "fix/" in branches
    assert "x = 1" in subprocess.run(["git", "show", "master:a.py"], cwd=wt, capture_output=True, text=True).stdout
    # registry marks it fixed
    reg = parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))
    assert reg[0]["status"] == "fixed" and reg[0]["branch"].startswith("fix/")


def test_fix_loop_does_not_commit_fl_scratch(tmp_path, monkeypatch):
    wt = _repo(tmp_path)

    def fake_fixer(finding, worktree):
        # simulate the real fixer: writes a scratch prompt file under .fl/ AND the real edit
        fl = Path(worktree) / ".fl"; fl.mkdir(exist_ok=True)
        (fl / "fix.md").write_text("prompt", encoding="utf-8")
        (Path(worktree) / "a.py").write_text("x = 2  # refactored\n", encoding="utf-8")
        return ("applied", 100)

    report_path = runner.run(
        wt, now="2026-07-03 0400", fixer=fake_fixer,
        skeptic=lambda f, w: ("confirmed", "good", 10),
        run_verify=lambda cfg, w: (True, "green"),
        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    reg = parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))
    assert reg[0]["status"] == "fixed"
    branch = reg[0]["branch"]
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", branch], cwd=wt,
                          capture_output=True, text=True).stdout
    assert ".fl" not in tree and "fix.md" not in tree   # scratch NOT committed
    assert "a.py" in tree


def test_fix_loop_reverts_and_marks_failed_on_verify_red(tmp_path, monkeypatch):
    wt = _repo(tmp_path)

    def fake_fixer(finding, worktree):
        (Path(worktree) / "a.py").write_text("BROKEN\n", encoding="utf-8")
        return ("applied", 100)

    # one-shot gate red -> escalate; rich also can't fix it (needs-human), tree left clean.
    def fake_rich(cfg, worktree, finding, *, run_verify):
        return ("needs-human", {}, 200, "exhausted 2 retries")

    monkeypatch.setattr(runner, "run_rich_refactor", fake_rich)
    runner.run(wt, now="2026-07-02 0300", fixer=fake_fixer,
               skeptic=lambda f, w: ("confirmed", "ok", 0),
               run_verify=lambda cfg, w: (False, "FAILED"),
               create_worktree=lambda root, br: root,
               remove_worktree=lambda root, wt: None)

    from registry import parse_registry
    reg = parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))
    assert reg[0]["status"] in ("failed", "needs-human")
    assert reg[0]["attempts"] == "1"
    assert "x = 1" in (wt / "a.py").read_text(encoding="utf-8")   # reverted


def _repo_bug(tmp_path):
    wt = _repo(tmp_path)
    reg = [{"fingerprint": "b:1", "file": "a.py", "dimension": "bug-hunt", "severity": "high",
            "fix_class": "bug", "summary": "bug", "status": "pending", "branch": "", "cost": "",
            "attempts": "0", "first_seen": "d", "last_seen": "d"}]
    (wt / "bug-registry.md").write_text(render_registry(reg), encoding="utf-8")
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "bug row")
    return wt


def test_runner_routes_bug_to_rich_bug_and_lands_it(tmp_path, monkeypatch):
    wt = _repo_bug(tmp_path)

    def fake_rich_bug(cfg, worktree, finding, *, run_verify):
        # simulate a rich-bug success: a test committed + the fix left uncommitted
        (Path(worktree) / "test_bug.py").write_text("def test_bug():\n    assert True\n", encoding="utf-8")
        import gitops
        gitops.commit_wip(worktree, "test: regression")
        (Path(worktree) / "a.py").write_text("x = 1\nfixed = True\n", encoding="utf-8")
        return ("fixed", {"approach": "ap", "justification": "why"}, 250, "gate passed")

    monkeypatch.setattr(runner, "run_rich_bug", fake_rich_bug)
    report_path = runner.run(
        wt, now="2026-07-03 0500", fixer=lambda f, w: ("no-op", 0),   # refactor fixer unused for a bug
        skeptic=lambda f, w: ("confirmed", "ok", 0),
        run_verify=lambda cfg, w: (True, "green"),
        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    text = report_path.read_text(encoding="utf-8")
    assert "fixed: 1" in text
    reg = parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))
    assert reg[0]["status"] == "fixed" and reg[0]["branch"].startswith("fix/")
    # the branch carries BOTH the test commit and the fix commit
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", reg[0]["branch"]], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "test_bug.py" in tree and "a.py" in tree
    show = subprocess.run(["git", "show", f"{reg[0]['branch']}:a.py"], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "fixed = True" in show


def test_runner_bug_needs_human(tmp_path, monkeypatch):
    wt = _repo_bug(tmp_path)

    def fake_rich_bug(cfg, worktree, finding, *, run_verify):
        return ("needs-human", {}, 120, "test-not-reproducing")

    monkeypatch.setattr(runner, "run_rich_bug", fake_rich_bug)
    runner.run(wt, now="2026-07-03 0500", fixer=lambda f, w: ("no-op", 0),
               skeptic=lambda f, w: ("confirmed", "ok", 0), run_verify=lambda cfg, w: (True, "green"),
               create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)
    reg = parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))
    assert reg[0]["status"] in ("failed", "needs-human")
    assert reg[0]["attempts"] == "1"


def test_runner_escalates_failed_oneshot_to_rich(tmp_path, monkeypatch):
    wt = _repo(tmp_path)

    def oneshot(finding, worktree):
        (Path(worktree) / "a.py").write_text("x = 2  # oneshot\n", encoding="utf-8")
        return ("applied", 50)

    # one-shot gate fails (run_verify red); the rich escalation succeeds and leaves an edit.
    def fake_rich(cfg, worktree, finding, *, run_verify):
        (Path(worktree) / "a.py").write_text("x = 3  # rich\n", encoding="utf-8")
        return ("fixed", {"approach": "ap", "justification": "why"}, 300, "gate passed")

    monkeypatch.setattr(runner, "run_rich_refactor", fake_rich)
    report_path = runner.run(
        wt, now="2026-07-03 0300", fixer=oneshot,
        skeptic=lambda f, w: ("confirmed", "ok", 0),
        run_verify=lambda cfg, w: (False, "FAILED"),     # one-shot gate red -> escalate
        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    text = report_path.read_text(encoding="utf-8")
    assert "fixed: 1" in text
    reg = parse_registry((wt / "bug-registry.md").read_text(encoding="utf-8"))
    assert reg[0]["status"] == "fixed" and reg[0]["branch"].startswith("fix/")
    # the rich edit (x = 3) is what got committed on the fix branch
    show = subprocess.run(["git", "show", f"{reg[0]['branch']}:a.py"], cwd=wt,
                          capture_output=True, text=True).stdout
    assert "x = 3" in show
