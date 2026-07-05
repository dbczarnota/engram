from __future__ import annotations

import subprocess
from pathlib import Path

_IGNORE = ("__pycache__/", ".pytest_cache/", ".ruff_cache/", ".mypy_cache/")


def _is_artifact(path: str) -> bool:
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    return (p.endswith((".pyc", ".pyo")) or any(m in p for m in _IGNORE)
            or base == ".coverage" or base.startswith(".coverage."))


def default_base(repo: Path) -> str:
    for candidate in ("master", "main"):
        result = subprocess.run(["git", "rev-parse", "--verify", candidate],
                                cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            return candidate
    return "master"


def branch_diffstat(repo: Path, branch: str, base: str = "master") -> tuple[list[str], int]:
    out = subprocess.run(["git", "diff", "--numstat", f"{base}..{branch}"],
                         cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"git diff {base}..{branch} failed: {out.stderr}")
    files: list[str] = []
    lines = 0
    for row in out.stdout.splitlines():
        parts = row.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        if _is_artifact(path):
            continue
        files.append(path)
        for n in (added, removed):
            if n.isdigit():
                lines += int(n)
    return (files, lines)


def branch_diff(repo: Path, branch: str, base: str = "master", *, max_chars: int = 12000) -> str:
    out = subprocess.run(["git", "diff", f"{base}..{branch}"],
                         cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"git diff {base}..{branch} failed: {out.stderr}")
    text = out.stdout
    return text[:max_chars]
