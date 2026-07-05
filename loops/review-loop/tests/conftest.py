from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_with_config(tmp_path: Path):
    """A repo dir containing a valid .reviewloop.yml. Returns (repo_root, write_config)."""
    def write_config(text: str) -> Path:
        (tmp_path / ".reviewloop.yml").write_text(text, encoding="utf-8")
        return tmp_path
    return tmp_path, write_config


VALID_YML = """\
verify:
  lint: "ruff check ."
  typecheck: "mypy ."
  test: "pytest -q"
backend: ["app/**"]
frontend: ["web/**"]
capabilities:
  logfire: "myrepo"
  db: true
max_iter: 2
budget_tokens: 400000
report_dir: "brain/projects/myrepo/loop-reports"
"""
