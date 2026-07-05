"""Chain driver: run the three loops end-to-end against ONE repo, sharing ONE registry.

    review-loop (detect -> UPSERT bug-registry.md)   # never resets; keeps pending/fixed/needs-human
      -> fix-loop (budgeted: fix at most --max-fixes; leftovers stay pending for next run)
        -> integrate-loop (tier the fixed branches into prod-safe / canary / needs-human)

Each loop runs as its own subprocess (`python loops/<loop> <repo> ...`) so their same-named modules
(runner.py / report.py / ...) never collide in one interpreter, and each keeps its own worktree/venv
isolation. The registry (target-repo-root `bug-registry.md`, gitignored) is the single hand-off between
stages: the chain itself NEVER touches it — review upserts, fix reads/mutates, integrate reads. Because
nothing resets, across runs new findings are ADDED to whatever remained pending; a budget-capped fix run
drains the backlog incrementally.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

_LOOPS = Path(__file__).resolve().parent


def _run_loop(loop: str, repo: Path, extra: list[str]) -> subprocess.CompletedProcess:
    """Run one loop as a subprocess: `python loops/<loop> <repo> [extra...]`. Inherits stdio so the
    loop's own [review-loop]/[fix-loop]/[integrate-loop] progress logging streams straight through."""
    return subprocess.run([sys.executable, str(_LOOPS / loop), str(repo), *extra], text=True)


def run_chain(repo_root, now: str | None = None, *, max_fixes: int | None = None,
              run_loop=_run_loop) -> dict:
    """Detect -> fix (budgeted) -> tier, sequentially, against repo_root. Returns each stage's exit code.
    Stops early if a stage fails (a red review/fix means the later stages have nothing trustworthy to do).
    The chain never reads or writes the registry itself — that is the loops' shared hand-off file."""
    repo_root = Path(repo_root)
    now = now or time.strftime("%Y-%m-%d %H%M")
    codes: dict = {}

    def _log(m):
        print(f"[chain] {m}", flush=True)

    _log(f"1/3 review-loop (detect -> upsert registry) on {repo_root.name}")
    codes["review"] = run_loop("review-loop", repo_root, []).returncode
    if codes["review"] != 0:
        _log(f"review-loop failed (exit {codes['review']}) — stopping chain")
        return codes

    fix_extra = ["--max-fixes", str(max_fixes)] if max_fixes is not None else []
    _log(f"2/3 fix-loop (budget: max_fixes={max_fixes})")
    codes["fix"] = run_loop("fix-loop", repo_root, fix_extra).returncode
    if codes["fix"] != 0:
        _log(f"fix-loop failed (exit {codes['fix']}) — stopping chain")
        return codes

    _log("3/3 integrate-loop (tier fixed branches)")
    codes["integrate"] = run_loop("integrate-loop", repo_root, []).returncode
    _log(f"chain done: {codes}")
    return codes


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="chain", description="run review -> fix -> integrate")
    ap.add_argument("repo", help="target repository path")
    ap.add_argument("--max-fixes", type=int, default=None,
                    help="budget for the fix stage: at most N candidates (rest stay pending)")
    ns = ap.parse_args()
    codes = run_chain(Path(ns.repo).resolve(), max_fixes=ns.max_fixes)
    raise SystemExit(0 if all(c == 0 for c in codes.values()) else 1)


if __name__ == "__main__":
    main()
