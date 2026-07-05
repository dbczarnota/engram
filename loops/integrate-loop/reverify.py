from __future__ import annotations

from pathlib import Path

import baseline                       # fix-loop baseline (on sys.path via conftest)
from triage import classify


def setup_bundle(cfg, bundle_wt: Path) -> tuple[bool, str]:
    """Resolve verify to the strong (Docker) path and run the project's setup (uv sync) ONCE in the bundle
    worktree, so the full suite can run there."""
    cfg.verify = baseline.resolve_verify(cfg.verify, docker_available=baseline.docker_available())
    return baseline.run_setup(cfg, bundle_wt)


def verify_green(cfg, bundle_wt: Path) -> tuple[bool, str]:
    """Run the resolved verify on the bundle worktree; green iff triage finds no failures, no
    un-runnable command, and no errors."""
    tr = classify(baseline.run_verify_detailed(cfg, bundle_wt))
    if tr.failures or tr.env_commands or tr.errors:
        detail = "; ".join([*(f.id for f in tr.failures), *sorted(tr.env_commands), *sorted(tr.errors)])
        return (False, detail[:200])
    return (True, "green")
