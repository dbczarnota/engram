from __future__ import annotations

import subprocess

import runner
from registry import render_registry


def _git(wt, *a):
    subprocess.run(["git", *a], cwd=wt, check=True, capture_output=True, text=True)


def _repo(tmp_path):
    wt = tmp_path
    _git(wt, "init", "-b", "master"); _git(wt, "config", "user.email", "t@t"); _git(wt, "config", "user.name", "t")
    (wt / ".reviewloop.yml").write_text(
        "verify:\n  test: echo ok\nreport_dir: reports\nbudget_tokens: 100000\n", encoding="utf-8")
    (wt / "a.py").write_text("x = 1\n", encoding="utf-8")
    (wt / "bug-registry.md").write_text(render_registry([]), encoding="utf-8")  # no candidates
    _git(wt, "add", "-A"); _git(wt, "commit", "-m", "init")
    return wt


def test_fix_loop_emits_live_progress_and_a_stop_line(tmp_path, capsys):
    wt = _repo(tmp_path)
    runner.run(wt, now="2026-07-03 0800",
               create_worktree=lambda root, br: root, remove_worktree=lambda root, wt: None)

    out = capsys.readouterr().out
    assert "[fix-loop]" in out
    assert any(line.startswith("[fix-loop] stop:") for line in out.splitlines())
