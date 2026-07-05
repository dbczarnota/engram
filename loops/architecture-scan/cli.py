from __future__ import annotations

import argparse
import time
from pathlib import Path

from runner import run


def main() -> None:
    ap = argparse.ArgumentParser(prog="architecture-scan")
    ap.add_argument("repo", help="path to the repo to scan")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    now = time.strftime("%Y-%m-%d %H%M")
    report = run(repo, now)
    print(f"architecture-scan done. Report: {report}")
