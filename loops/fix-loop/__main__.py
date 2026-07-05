from __future__ import annotations

import sys
from pathlib import Path

# Reuse review-loop modules (registry/verify/adversarial/worktree/claude helpers).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))  # fix-loop's own runner.py must win over review-loop's
_REVIEW_LOOP = _HERE.parent / "review-loop"
if str(_REVIEW_LOOP) not in sys.path:
    sys.path.append(str(_REVIEW_LOOP))

import argparse  # noqa: E402
import time  # noqa: E402
from runner import run  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(prog="fix-loop")
    ap.add_argument("repo", help="target repository path")
    ap.add_argument("--max-fixes", type=int, default=None,
                    help="budget: attempt at most N candidates this run (rest stay pending)")
    ns = ap.parse_args()
    repo = Path(ns.repo).resolve()
    now = time.strftime("%Y-%m-%d %H%M")
    report = run(repo, now, max_fixes=ns.max_fixes)
    print(f"fix-loop done. Report: {report}")


if __name__ == "__main__":
    main()
