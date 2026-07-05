from __future__ import annotations

import subprocess
from pathlib import Path

import runner
from registry import render_registry


class _F:
    fingerprint = "backend/x.py:foo:n1"
    file = "backend/x.py"
    dimension = "perf"
    severity = "medium"
    summary = "N+1 in foo"


def test_render_dossier_with_plan_has_analysis():
    from dossier import render_dossier
    txt = render_dossier(_F(), "gate: verify RED — pyright",
                         {"root_cause": "loop per row", "approach": "batch IN-query",
                          "alternatives": "join", "justification": "fewer round-trips"})
    assert "N+1 in foo" in txt and "verify RED" in txt
    assert "loop per row" in txt and "batch IN-query" in txt and "fewer round-trips" in txt


def test_render_dossier_without_plan_still_has_finding_and_reason():
    from dossier import render_dossier
    txt = render_dossier(_F(), "no change applied", None)
    assert "N+1 in foo" in txt and "no change applied" in txt


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    wt = tmp_path
    _git(wt, "init", "-b", "master"); _git(wt, "config", "user.email", "t@t"); _git(wt, "config", "user.name", "t")
    (wt / ".reviewloop.yml").write_text(
        'verify:\n  check: python -c "pass"\nreport_dir: reports\nbudget_tokens: 100000\n', encoding="utf-8")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    reg = [{"fingerprint": "a.py:foo:n1", "file": "a.py", "dimension": "perf", "severity": "medium",
            "fix_class": "refactor", "summary": "N+1 in foo", "status": "pending", "branch": "",
            "cost": "", "attempts": "0", "first_seen": "d", "last_seen": "d"}]
    (wt / "bug-registry.md").write_text(render_registry(reg), encoding="utf-8")
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "init")
    return wt


def test_runner_writes_dossier_on_escalation_needs_human(tmp_path, monkeypatch):
    wt = _repo(tmp_path)

    def oneshot(finding, worktree):
        (Path(worktree) / "a.py").write_text("x = 2  # attempt\n", encoding="utf-8")
        return ("applied", 50)

    # one-shot gate fails (verify red) -> escalate; rich returns needs-human WITH a plan
    def fake_rich(cfg, worktree, finding, *, run_verify):
        return ("needs-human", {"root_cause": "loop per row", "approach": "batch",
                                "alternatives": "join", "justification": "fewer trips"}, 200, "rich: exhausted")

    monkeypatch.setattr(runner, "run_rich_refactor", fake_rich)
    report = runner.run(wt, now="2026-07-03 2000", fixer=oneshot,
                        skeptic=lambda f, w: ("confirmed", "ok", 0),
                        run_verify=lambda cfg, w: (False, "RED"),
                        create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    # a dossier file was written under reports/needs-human/ and referenced in the report
    nh_dir = wt / "reports" / "needs-human"
    files = list(nh_dir.glob("*.md"))
    assert len(files) == 1
    dossier_txt = files[0].read_text(encoding="utf-8")
    assert "loop per row" in dossier_txt and "batch" in dossier_txt   # the loop's plan is preserved
    assert "dossier:" in report.read_text(encoding="utf-8")


def test_render_dossier_includes_wip_branch_when_present():
    from dossier import render_dossier
    txt = render_dossier(_F(), "gate red", {"root_cause": "rc", "approach": "ap"}, wip="wip/a-123")
    assert "wip/a-123" in txt and "git checkout wip/a-123" in txt


def test_render_dossier_notes_no_wip_when_absent():
    from dossier import render_dossier
    txt = render_dossier(_F(), "no change applied", None, wip=None)
    assert "not preserved" in txt
