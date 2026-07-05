from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from verify import _run as _default_run   # review-loop per-command runner (on sys.path via conftest)


def docker_available() -> bool:
    """Is a Docker daemon reachable? Used to pick the strong (Docker/testcontainers) verify path vs a
    graceful non-Docker fallback."""
    try:
        proc = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=20)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def resolve_verify(verify: dict, *, docker_available: bool) -> dict[str, str]:
    """Flatten a verify block whose values may be either a plain command string OR a capability variant
    `{requires: docker, with: <cmd>, without: <cmd>}`. With a variant, pick `with` when the capability is
    present, else `without` — so the strong path (e.g. full pytest incl. testcontainers) runs by default
    and degrades gracefully to the light path (e.g. `pytest -m 'not requires_docker'`) when Docker is
    absent. Everything downstream (baseline/gate) sees a flat {name: command} and is unchanged."""
    out: dict[str, str] = {}
    for name, val in (verify or {}).items():
        if isinstance(val, dict):
            if val.get("requires") == "docker":
                out[name] = val["with"] if docker_available else val["without"]
            else:
                out[name] = val.get("with") or val.get("without") or ""
        else:
            out[name] = val
    return out


@dataclass
class CommandResult:
    name: str
    command: str
    exit_code: int
    output: str


def run_verify_detailed(cfg, worktree: Path, *, run=None) -> list[CommandResult]:
    """Run each cfg.verify command and keep the per-command (exit_code, output) — the structured input
    triage needs. Unlike review-loop's run_verify (which collapses to a single bool+detail), this keeps
    each command separate so failures can be classified and identified individually."""
    runner = run or _default_run
    results: list[CommandResult] = []
    for name, command in (cfg.verify or {}).items():
        code, output = runner(command, worktree)
        results.append(CommandResult(name=name, command=command, exit_code=code, output=output or ""))
    return results


def run_setup(cfg, worktree: Path, *, run=None) -> tuple[bool, str]:
    """Bootstrap the project's environment inside the (bare) fix-loop worktree before any verify runs —
    e.g. `uv sync` to materialise `.venv` so pyright/pytest resolve imports. Runs each cfg.setup command
    in order; the FIRST failure aborts (returns False + detail). No setup configured => (True, ...)."""
    runner = run or _default_run
    for name, command in (getattr(cfg, "setup", None) or {}).items():
        code, output = runner(command, worktree)
        if code != 0:
            tail = "\n".join((output or "").strip().splitlines()[-10:])
            return (False, f"[{name}] `{command}` exit {code}\n{tail}")
    return (True, "setup ok")
