from __future__ import annotations

import subprocess
from pathlib import Path

from report import Finding, IterationResult
from runner import run
from tests.conftest import VALID_YML
from tests.fakes import make_iterate


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / ".reviewloop.yml").write_text(
        VALID_YML.replace("brain/projects/myrepo/loop-reports", "reports"),
        encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)


def test_runner_emits_live_progress(tmp_path, capsys):
    _init_repo(tmp_path)
    finding = Finding(fingerprint="test-finding", file="test.py", line=10,
                      dimension="bug-hunt", severity="high", layer="backend",
                      summary="test finding summary")
    iterate = make_iterate([
        IterationResult(fingerprints={"test"}, findings=[finding], parsed=True),
        IterationResult(fingerprints=set(), parsed=True),  # clean -> stop
    ])
    run(tmp_path, iterate, now="2026-07-01 03:00")

    out = capsys.readouterr().out
    assert "[review-loop]" in out
    assert any("registry:" in line for line in out.splitlines())
