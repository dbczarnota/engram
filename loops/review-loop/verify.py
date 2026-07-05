from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from config import ReviewLoopConfig

_TIMEOUT_S = 600  # verify (tests) can be slow; a hung command becomes a failure, not a hang


def _run(command: str, worktree: Path) -> tuple[int, str]:
    """Run one verify command in the worktree. Returns (exit_code, combined_output)."""
    parts = shlex.split(command or "")
    if not parts:
        return (126, "empty verify command")
    try:
        proc = subprocess.run(parts, cwd=worktree, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=_TIMEOUT_S)
        return (proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
    except FileNotFoundError as e:
        return (127, f"command not found: {e}")
    except subprocess.TimeoutExpired:
        return (124, f"timed out after {_TIMEOUT_S}s")
    except OSError as e:
        return (126, f"could not run: {e}")


def run_verify(cfg: ReviewLoopConfig, worktree: Path, *, run=_run) -> tuple[bool, str]:
    """Run every cfg.verify command in the worktree. Returns (all_passed, detail). A command that
    exits non-zero OR cannot run counts as failure (a verify we can't run does not prove behavior is
    preserved). `run` is injectable so tests don't spawn processes."""
    if not cfg.verify:
        return (True, "no verify commands configured")
    failures: list[str] = []
    for name, command in cfg.verify.items():
        code, output = run(command, worktree)
        if code != 0:
            tail = "\n".join((output or "").strip().splitlines()[-15:])
            failures.append(f"[{name}] `{command}` exit {code}\n{tail}")
    if failures:
        return (False, "\n\n".join(failures))
    return (True, "all verify commands passed")
