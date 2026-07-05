from __future__ import annotations

import subprocess

import pytest

import gitmeta


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def test_branch_diffstat_counts_files_and_lines(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "checkout", "-b", "fix/x")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir(); (tmp_path / "__pycache__" / "a.pyc").write_bytes(b"\x00")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "fix")

    files, lines = gitmeta.branch_diffstat(tmp_path, "fix/x")
    assert files == ["a.py"]            # pyc artifact ignored
    assert lines == 2                   # two added lines


def test_branch_diffstat_raises_on_git_failure(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")

    with pytest.raises(RuntimeError):
        gitmeta.branch_diffstat(tmp_path, "does-not-exist")


def test_default_base_prefers_master_then_main(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    assert gitmeta.default_base(tmp_path) == "master"


def test_default_base_falls_back_to_main(tmp_path):
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    assert gitmeta.default_base(tmp_path) == "main"


def test_branch_diff_returns_text_and_raises_on_failure(tmp_path):
    _git(tmp_path, "init", "-b", "master")
    _git(tmp_path, "config", "user.email", "t@t"); _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "checkout", "-b", "fix/x")
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "-A"); _git(tmp_path, "commit", "-m", "fix")

    text = gitmeta.branch_diff(tmp_path, "fix/x")
    assert "y = 2" in text

    with pytest.raises(RuntimeError):
        gitmeta.branch_diff(tmp_path, "does-not-exist")
