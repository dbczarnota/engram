from __future__ import annotations

import sqlite3
from pathlib import Path

from models import Candidate


def _norm(p: str) -> str:
    return p.replace("\\", "/").lower()


# Directory markers whose contents are never app code we'd propose refactoring: dependencies (pip/npm),
# virtualenvs, and git-worktree copies. CRG can index these (a Windows `update` bug re-adds node_modules/
# .venv/.worktrees between commits — see hooks/install-crg-hook.ps1), so discovery must exclude them
# defensively even when the graph is dirty. `.claude/worktrees/` and `.worktrees/` are distinct markers.
_NOISE_MARKERS = (
    ".claude/worktrees/", ".worktrees/", "node_modules/", "site-packages/", ".venv/",
)


def _is_noise(file_path: str) -> bool:
    p = _norm(file_path)
    if any(m in p for m in _NOISE_MARKERS):
        return True
    base = p.rsplit("/", 1)[-1]
    return "/tests/" in p or base.startswith("test_") or base.endswith("_test.py")


def _in_scope(file_path: str, repo_root: Path, paths: list[str]) -> bool:
    p, root = _norm(file_path), _norm(str(repo_root))
    if not p.startswith(root):
        return False
    if not paths:
        return True
    rel = p[len(root):].lstrip("/")
    for sp in paths:
        s = _norm(sp).lstrip("/").rstrip("/")
        if rel == s or rel.startswith(s + "/"):
            return True
    return False


def _rel(file_path: str, repo_root: Path) -> str:
    p, root = _norm(file_path), _norm(str(repo_root))
    return p[len(root):].lstrip("/") if p.startswith(root) else _norm(file_path)


def _degrees(conn: sqlite3.Connection) -> dict[str, int]:
    deg: dict[str, int] = {}
    for col in ("source_qualified", "target_qualified"):
        for qn, c in conn.execute(
                f"SELECT {col}, COUNT(*) FROM edges WHERE kind='CALLS' GROUP BY {col}"):
            deg[qn] = deg.get(qn, 0) + c
    return deg


def discover_candidates(db_path: Path, repo_root: Path, *, paths=(), min_lines: int = 45,
                        top_k: int = 3) -> list[Candidate]:
    conn = sqlite3.connect(str(db_path))
    try:
        deg = _degrees(conn)
        rows = conn.execute(
            "SELECT qualified_name, file_path, line_start, line_end FROM nodes "
            "WHERE kind='Function' AND (line_end - line_start + 1) >= ?", (min_lines,)).fetchall()
    finally:
        conn.close()
    out: list[Candidate] = []
    for qn, fp, ls, le in rows:
        if _is_noise(fp) or not _in_scope(fp, repo_root, list(paths)):
            continue
        lines = (le or ls) - ls + 1
        degree = deg.get(qn, 0)
        out.append(Candidate(qualified_name=qn, file=_rel(fp, repo_root), line_start=ls,
                             line_end=le or ls, lines=lines, degree=degree,
                             signals=["large-function"], score=float(lines + 3 * degree)))
    out.sort(key=lambda c: c.score, reverse=True)
    return out[:top_k]
