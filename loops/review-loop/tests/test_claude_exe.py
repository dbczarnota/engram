from __future__ import annotations

import pytest

import claude_iterate


def test_claude_exe_uses_shutil_which(monkeypatch):
    monkeypatch.setattr(claude_iterate.shutil, "which", lambda name: r"C:\npm\claude.CMD")
    assert claude_iterate._claude_exe() == r"C:\npm\claude.CMD"


def test_claude_exe_raises_clearly_when_missing(monkeypatch):
    monkeypatch.setattr(claude_iterate.shutil, "which", lambda name: None)
    with pytest.raises(claude_iterate.ClaudeNotFound, match="not found on PATH"):
        claude_iterate._claude_exe()
