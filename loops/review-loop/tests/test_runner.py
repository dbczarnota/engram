from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from report import Finding, IterationResult
from runner import run, _rel_static_file
from tests.conftest import VALID_YML
from tests.fakes import make_iterate


def test_rel_static_file_strips_repo_root_windows_drive():
    root = Path(r"C:/Users/x/myrepo")
    # ruff emits an uppercase drive, pyright a lowercase one - both must relativise
    assert _rel_static_file(r"C:\Users\x\myrepo\backend\api\articles.py:45 SIM105 use suppress",
                            root) == "backend/api/articles.py"
    assert _rel_static_file(r"c:\Users\x\myrepo\agents\runner.py:162 error [reportArg] bad",
                            root) == "agents/runner.py"


def test_rel_static_file_unparseable_is_empty():
    assert _rel_static_file("no file here", Path("C:/repo")) == ""


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / ".reviewloop.yml").write_text(
        VALID_YML.replace("brain/projects/myrepo/loop-reports", "reports"),
        encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)


def test_run_writes_report_and_stops_on_clean(tmp_path):
    _init_repo(tmp_path)
    iterate = make_iterate([
        IterationResult(fingerprints={"a"}, findings=[
            Finding(fingerprint="fix a", file="a.py", line=1, dimension="bug-hunt",
                    severity="low", layer="backend", summary="fix a")], tokens=100),
        IterationResult(fingerprints=set(), tokens=50),  # clean -> stop
    ])
    report_path = run(tmp_path, iterate, now="2026-07-01 03:00")
    assert report_path.is_file()
    text = report_path.read_text(encoding="utf-8")
    assert "read: false" in text
    assert "fix a" in text
    assert "stop_reason: clean" in text


def test_run_respects_max_iter_override(tmp_path):
    _init_repo(tmp_path)
    iterate = make_iterate([IterationResult(fingerprints={f"f{i}"}, tokens=1) for i in range(5)])
    report_path = run(tmp_path, iterate, now="2026-07-01 03:00", max_iter_override=1)
    assert "stop_reason: max_iter" in report_path.read_text(encoding="utf-8")


def test_run_rejects_max_iter_below_one(tmp_path):
    _init_repo(tmp_path)
    iterate = make_iterate([IterationResult(fingerprints={"a"}, tokens=1)])
    with pytest.raises(ValueError, match="max_iter must be >= 1, got 0"):
        run(tmp_path, iterate, now="2026-07-01 03:00", max_iter_override=0)
    report_dir = tmp_path / "reports"
    assert not report_dir.exists() or not list(report_dir.iterdir())


def test_run_cleans_up_worktree(tmp_path):
    _init_repo(tmp_path)
    iterate = make_iterate([IterationResult(fingerprints=set())])
    run(tmp_path, iterate, now="2026-07-01 03:00")
    out = subprocess.run(["git", "worktree", "list"], cwd=tmp_path,
                         capture_output=True, text=True).stdout
    assert ".rl-worktrees" not in out


def test_run_no_output_is_not_reported_as_clean(tmp_path):
    _init_repo(tmp_path)
    iterate = make_iterate([
        IterationResult(parsed=False, raw="claude produced no findings file"),
    ])
    report_path = run(tmp_path, iterate, now="2026-07-01 03:00")
    text = report_path.read_text(encoding="utf-8")
    assert "stop_reason: no-output" in text
    assert "clean" not in text.split("stop_reason:")[1].splitlines()[0]
    assert "NOT a clean pass" in text
    # raw agent output is persisted next to the report for debugging
    sidecar = report_path.with_suffix(".agent.log")
    assert sidecar.is_file()
    assert "no findings file" in sidecar.read_text(encoding="utf-8")


def test_runner_maps_rate_limited_to_stop_reason(tmp_path):
    _init_repo(tmp_path)

    def fake_iterate(cfg, worktree, i):
        return IterationResult(parsed=False, failure_kind="rate-limited",
                               error_detail="You've hit your session limit resets 5pm")

    report_path = run(tmp_path, fake_iterate, now="2026-07-02 1200")
    text = report_path.read_text(encoding="utf-8")
    assert "stop_reason: rate-limited" in text


def test_run_includes_static_analysis_findings(tmp_path):
    import sys
    import shlex
    import yaml
    _init_repo(tmp_path)
    ruff_json = '[{"code":"F401","message":"unused","filename":"a.py","location":{"row":1,"column":1}}]'
    # fake "ruff" = a python script that prints ruff-shaped JSON (avoids -c quoting issues)
    script = tmp_path / "fakeruff.py"
    script.write_text(f"print({ruff_json!r})", encoding="utf-8")
    ruff_cmd = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    # add the analysis block via a yaml round-trip so command quoting is correct on any OS
    cfg_path = tmp_path / ".reviewloop.yml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["analysis"] = {"ruff": ruff_cmd}
    cfg_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "add analysis"], cwd=tmp_path, check=True)
    iterate = make_iterate([IterationResult(fingerprints=set())])  # clean LLM pass
    report_path = run(tmp_path, iterate, now="2026-07-01 03:00")
    text = report_path.read_text(encoding="utf-8")
    assert "## Static analysis" in text
    assert "a.py:1 F401 unused" in text
    assert "analysis_findings: 1" in text


def test_run_analysis_runs_against_repo_root_not_worktree(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    import yaml
    cfg_path = tmp_path / ".reviewloop.yml"
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["analysis"] = {"ruff": "unused-cmd"}  # command irrelevant; we intercept run_analysis
    cfg_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "analysis"], cwd=tmp_path, check=True)

    seen = {}
    import runner
    monkeypatch.setattr(runner, "run_analysis",
                        lambda cfg, path: (seen.setdefault("path", path), ([], []))[1])
    run(tmp_path, make_iterate([IterationResult(fingerprints=set())]), now="2026-07-01 03:00")
    # analysis must run against the repo root, NOT the .rl-worktrees/... worktree
    assert seen["path"] == tmp_path
    assert ".rl-worktrees" not in str(seen["path"])


def test_runner_includes_log_sweep_when_logfire(tmp_path, monkeypatch):
    import runner
    import yaml
    _init_repo(tmp_path)
    # make the config declare a logfire project
    cfgfile = tmp_path / ".reviewloop.yml"
    data = yaml.safe_load(cfgfile.read_text(encoding="utf-8"))
    data["capabilities"]["logfire"] = "demoproj"
    cfgfile.write_text(yaml.safe_dump(data), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "add logfire"], cwd=tmp_path, check=True)
    monkeypatch.setattr(runner, "run_log_sweep", lambda cfg: (["prod ValueError: boom"], []))

    def fake_iterate(cfg, worktree, i):
        from report import IterationResult
        return IterationResult(fingerprints=set(), parsed=True)

    report_path = runner.run(tmp_path, fake_iterate, now="2026-07-02 1200")
    text = report_path.read_text(encoding="utf-8")
    assert "## Log errors (Logfire)" in text
    assert "prod ValueError: boom" in text


def test_runner_includes_vault_todos(tmp_path, monkeypatch):
    import runner
    _init_repo(tmp_path)
    monkeypatch.setattr(runner, "run_vault_todo_sweep",
                        lambda cfg, repo_root: (["Fix the deferred thing"], []))

    def fake_iterate(cfg, worktree, i):
        from report import IterationResult
        return IterationResult(fingerprints=set(), parsed=True)

    report_path = runner.run(tmp_path, fake_iterate, now="2026-07-02 1200")
    text = report_path.read_text(encoding="utf-8")
    assert "## Vault TODOs" in text
    assert "Fix the deferred thing" in text


def test_runner_marks_stop_reason_partial_on_layer_failure(tmp_path):
    from report import IterationResult
    _init_repo(tmp_path)

    def fake_iterate(cfg, worktree, i):
        # a clean-ish parsed result that nonetheless had one layer fail
        return IterationResult(fingerprints=set(), parsed=True,
                               layer_failures=[("frontend", "rate-limited: session cap")])

    report_path = run(tmp_path, fake_iterate, now="2026-07-02 1300", max_iter_override=1)
    text = report_path.read_text(encoding="utf-8")
    assert "stop_reason: clean-partial" in text


def test_runner_runs_adversarial_verify(tmp_path, monkeypatch):
    import runner
    from report import IterationResult
    _init_repo(tmp_path)

    candidate = Finding(fingerprint="candidate", file="a.py", line=1, dimension="bug-hunt",
                        severity="low", layer="backend", summary="candidate")

    def fake_iterate(cfg, worktree, i):
        return IterationResult(fingerprints={"a"}, findings=[candidate], parsed=True)

    def fake_verify(worktree, findings):
        return ([], [(candidate, "false positive")], 123)  # refute it

    monkeypatch.setattr(runner, "verify_findings", fake_verify)
    report_path = runner.run(tmp_path, fake_iterate, now="2026-07-02 1400", max_iter_override=1)
    text = report_path.read_text(encoding="utf-8")
    assert "## Filtered out" in text
    assert "false positive" in text
    assert "findings: 0" in text
    assert "skeptic_tokens: 123" in text


def test_runner_writes_registry_with_findings(tmp_path):
    """Runner writes findings to bug-registry.md at repo_root/bug-registry.md"""
    _init_repo(tmp_path)
    finding = Finding(fingerprint="test-finding", file="test.py", line=10,
                      dimension="bug-hunt", severity="high", layer="backend",
                      summary="test finding summary")
    iterate = make_iterate([
        IterationResult(fingerprints={"test"}, findings=[finding], parsed=True),
        IterationResult(fingerprints=set(), parsed=True),  # clean -> stop
    ])
    report_path = run(tmp_path, iterate, now="2026-07-01 03:00")
    assert report_path.is_file()

    # Registry should be written to repo_root / "bug-registry.md"
    # (report_dir is "reports", so (repo_root / "reports").parent / "bug-registry.md" = repo_root / "bug-registry.md")
    registry_path = tmp_path / "bug-registry.md"
    assert registry_path.is_file(), f"Registry not found at {registry_path}"

    registry_text = registry_path.read_text(encoding="utf-8")
    assert "test-finding" in registry_text
    assert "test.py" in registry_text
    assert "test finding summary" in registry_text
    assert "pending" in registry_text  # new findings should be pending


def test_runner_report_contains_bucket_section(tmp_path):
    """The report render must include the Bucket section built from reconciled registry rows."""
    _init_repo(tmp_path)
    finding = Finding(fingerprint="bucket-finding", file="test.py", line=10,
                      dimension="bug-hunt", severity="high", layer="backend",
                      summary="test finding summary")
    iterate = make_iterate([
        IterationResult(fingerprints={"test"}, findings=[finding], parsed=True),
        IterationResult(fingerprints=set(), parsed=True),  # clean -> stop
    ])
    report_path = run(tmp_path, iterate, now="2026-07-01 03:00")
    text = report_path.read_text(encoding="utf-8")
    assert "## Bucket" in text


def test_runner_registry_excludes_refuted_findings(tmp_path, monkeypatch):
    # The backlog must hold adversarial SURVIVORS only — a refuted false-positive must not enter it.
    import runner
    from report import IterationResult, Finding
    _init_repo(tmp_path)
    keep = Finding(fingerprint="keep:1", file="a.py", line=1, dimension="dedup",
                   severity="low", layer="backend", summary="real dup")
    drop = Finding(fingerprint="drop:1", file="b.py", line=1, dimension="perf",
                   severity="low", layer="backend", summary="bogus")

    def fake_iterate(cfg, worktree, i):
        return IterationResult(fingerprints={"keep:1", "drop:1"}, parsed=True, findings=[keep, drop])

    monkeypatch.setattr(runner, "verify_findings",
                        lambda wt, findings: ([keep], [(drop, "false positive")], 0))
    runner.run(tmp_path, fake_iterate, now="2026-07-02 1600", max_iter_override=1)
    text = (tmp_path / "bug-registry.md").read_text(encoding="utf-8")
    assert "keep:1" in text
    assert "drop:1" not in text
