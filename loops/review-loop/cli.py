from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

from claude_iterate import claude_iterate
from runner import run


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="review-loop")
    p.add_argument("repo", help="path to the target repo (must contain .reviewloop.yml)")
    p.add_argument("--iter", type=int, default=None, help="override max_iter")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    ns = parse_args(argv if argv is not None else __import__("sys").argv[1:])
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    report = run(Path(ns.repo), claude_iterate, now=now, max_iter_override=ns.iter)
    print(f"review-loop done. Report: {report}")
