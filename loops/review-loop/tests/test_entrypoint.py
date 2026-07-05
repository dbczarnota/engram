from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def test_entrypoint_help_runs_as_documented():
    """The documented invocation is `python __main__.py <repo> [--iter N]` run from the
    package dir. `-m review-loop` can't work (hyphen isn't a valid module name), and
    `from cli import main` only resolves this way because the package dir is cwd and
    lands on sys.path[0]. This proves the wiring the unit tests never exercise."""
    proc = subprocess.run(
        [sys.executable, "__main__.py", "--help"],
        cwd=PACKAGE_DIR, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "--iter" in proc.stdout
