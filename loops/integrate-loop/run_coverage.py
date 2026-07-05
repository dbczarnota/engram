from __future__ import annotations

from pathlib import Path

import coverage as _coverage
from verify import _run as _default_run     # review-loop per-command runner (on sys.path)


def collect(cfg, bundle_wt: Path, *, run=None):
    cmd = getattr(cfg, "coverage", "") or ""
    if not cmd:
        return None                                 # coverage disabled
    runner = run or _default_run
    code, _out = runner(cmd, bundle_wt)
    if code != 0:
        return None                                 # coverage run failed -> fail-safe (no prod-safe kept)
    xml = bundle_wt / "coverage.xml"
    if not xml.is_file():
        return None
    text = xml.read_text(encoding="utf-8")
    if not text.strip():
        return None
    try:
        return _coverage.parse_cobertura(text)
    except Exception:                               # malformed/truncated XML -> fail-safe (demote), never crash
        return None


def collect_for_branch(cfg, repo, branch, *, open_bundle=None, setup_bundle=None, close_bundle=None,
                       collect=None):
    """Coverage for an already-published bundle branch: open a FRESH detached worktree at `branch` (the
    Plan-B bundle worktree is already closed), run setup once, run `collect`, then close. Returns the
    coverage map or None (disabled/failed) — fail-safe."""
    import bundle as _bundle
    import reverify as _reverify
    open_bundle = open_bundle or _bundle.open_bundle
    setup_bundle = setup_bundle or _reverify.setup_bundle
    close_bundle = close_bundle or _bundle.close_bundle
    collect = collect or globals()["collect"]
    if not (getattr(cfg, "coverage", "") or ""):
        return None
    wt = open_bundle(repo, f"coverage-{branch.replace('/', '-')}", ref=branch)
    try:
        ok, _detail = setup_bundle(cfg, wt)
        if not ok:
            return None
        return collect(cfg, wt)
    finally:
        close_bundle(repo, wt)
