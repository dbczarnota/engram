from __future__ import annotations

from config import ReviewLoopConfig
from vaulttodo import run_vault_todo_sweep


def _cfg(report_dir="loop-reports"):
    return ReviewLoopConfig(verify={}, report_dir=report_dir, max_iter=1, budget_tokens=1)


def test_no_todos_file_returns_empty(tmp_path):
    assert run_vault_todo_sweep(_cfg(), tmp_path) == ([], [])


def test_extracts_unchecked_items(tmp_path):
    (tmp_path / "todos.md").write_text(
        "# Todos\n\n- [ ] **Fix the thing** `#deferred` blah\n- [x] done item\n- [ ] second\n",
        encoding="utf-8")
    findings, errors = run_vault_todo_sweep(_cfg(), tmp_path)
    assert errors == []
    assert any("Fix the thing" in f for f in findings)
    assert any("second" in f for f in findings)
    assert not any("done item" in f for f in findings)   # checked excluded
    assert not any("**" in f for f in findings)           # bold stripped


def test_caps_and_notes_overflow(tmp_path):
    body = "\n".join(f"- [ ] item {i}" for i in range(40))
    (tmp_path / "todos.md").write_text(body, encoding="utf-8")
    findings, errors = run_vault_todo_sweep(_cfg(), tmp_path)
    assert len(findings) == 30
    assert any("40 open items" in e for e in errors)


def test_never_writes_todos(tmp_path):
    f = tmp_path / "todos.md"
    original = "- [ ] keep me\n"
    f.write_text(original, encoding="utf-8")
    run_vault_todo_sweep(_cfg(), tmp_path)
    assert f.read_text(encoding="utf-8") == original      # unchanged
