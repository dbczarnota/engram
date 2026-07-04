"""Weekly CRG graph maintenance: prune dependency/venv/worktree nodes + VACUUM every registered repo's
`.code-review-graph/graph.db` to reclaim free pages.

Why this exists: the per-commit hook (`install-crg-hook.ps1`) prunes junk each commit but never VACUUMs
(VACUUM rewrites the whole DB — too slow to run on every commit), so graph.db files slowly accumulate free
pages (brain hit 327 MB for 1.1k nodes). This sweep runs weekly (Windows scheduled task) to reclaim them,
and also prunes any repo that hasn't committed recently. Best-effort; never raises fatally. Standalone —
only Python stdlib. See lessons/code-review-graph.md.

Run:  python hooks/crg_maintenance.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

# Same junk markers as the post-commit prune (install-crg-hook.ps1). Deps, virtualenvs, git-worktree
# copies (bare `.worktrees/` AND `.claude/worktrees/`), vendored editor plugins.
PATS = ("%node_modules%", "%site-packages%", "%.venv%", "%.worktrees%", "%.claude%", "%.obsidian%")

_ORPHAN_CLEANUP = (
    "DELETE FROM embeddings WHERE qualified_name NOT IN (SELECT qualified_name FROM nodes)",
    "DELETE FROM risk_index WHERE node_id NOT IN (SELECT id FROM nodes)",
    "DELETE FROM flow_memberships WHERE node_id NOT IN (SELECT id FROM nodes)",
    "INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')",
)


def sweep_db(db: str) -> tuple[float, float, int]:
    """Prune junk nodes/edges then VACUUM one graph.db. Returns (before_mb, after_mb, pruned_nodes).
    Cleanup of secondary tables that may not exist is best-effort (OperationalError is swallowed)."""
    before = os.path.getsize(db) / 1e6
    where = " OR ".join("file_path LIKE ?" for _ in PATS)
    con = sqlite3.connect(db, timeout=30)
    try:
        pruned = con.execute(f"SELECT COUNT(*) FROM nodes WHERE {where}", PATS).fetchone()[0]
        if pruned:
            con.execute(f"DELETE FROM edges WHERE {where}", PATS)
            con.execute(f"DELETE FROM nodes WHERE {where}", PATS)
            for stmt in _ORPHAN_CLEANUP:
                try:
                    con.execute(stmt)
                except sqlite3.OperationalError:
                    pass
            con.commit()
        con.execute("VACUUM")
    finally:
        con.close()
    return before, os.path.getsize(db) / 1e6, pruned


def _registry_repos() -> list[str]:
    reg = os.path.expanduser(os.path.join("~", ".code-review-graph", "registry.json"))
    try:
        with open(reg, encoding="utf-8") as f:
            return [r["path"] for r in (json.load(f).get("repos") or [])]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _all_repos() -> list[str]:
    # Registered repos + the brain vault itself (the script lives at <brain>/hooks/, so its repo is
    # parents[1]); brain is queried but usually not in the CRG registry.
    brain = str(Path(__file__).resolve().parents[1])
    seen, out = set(), []
    for p in [*_registry_repos(), brain]:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def main() -> int:
    total_reclaimed = 0.0
    for repo in _all_repos():
        db = os.path.join(repo, ".code-review-graph", "graph.db")
        name = os.path.basename(repo.rstrip("\\/"))
        if not os.path.exists(db):
            continue
        try:
            before, after, pruned = sweep_db(db)
            total_reclaimed += before - after
            print(f"[crg-vacuum] {name:22} {before:>7.0f}MB -> {after:>6.0f}MB  (pruned {pruned} junk nodes)",
                  flush=True)
        except Exception as e:  # never let one repo abort the sweep
            print(f"[crg-vacuum] {name:22} SKIPPED: {e}", flush=True)
    print(f"[crg-vacuum] done — reclaimed {total_reclaimed:.0f} MB total", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
