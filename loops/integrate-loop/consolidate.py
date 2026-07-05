from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import bundle as _bundle
import reverify as _reverify


def _log(msg):
    print(f"[integrate-loop] {msg}", flush=True)


@dataclass
class BundleResult:
    tier: str
    branch: str | None
    included: list = field(default_factory=list)
    pulled: list = field(default_factory=list)      # merged but broke the bundle (demote -> needs-human)
    conflicts: list = field(default_factory=list)    # could not merge (kept as own branch)


def consolidate(repo: Path, cfg, tier: str, fixes: list, *,
                open_bundle=_bundle.open_bundle, try_merge=_bundle.try_merge,
                revert_last=_bundle.revert_last, finalize=_bundle.finalize,
                close_bundle=_bundle.close_bundle, head_sha=_bundle.head_sha,
                setup_bundle=_reverify.setup_bundle,
                verify_green=_reverify.verify_green) -> BundleResult:
    res = BundleResult(tier=tier, branch=None)
    wt = open_bundle(repo, f"integrate-{tier}")
    try:
        ok, _detail = setup_bundle(cfg, wt)
        if not ok:
            res.pulled = list(fixes)                 # can't verify -> nothing shippable this run
            _log(f"bundle {tier}: setup FAILED — all {len(fixes)} fix(es) held for human")
            return res
        n = len(fixes)
        for k, fix in enumerate(fixes, 1):
            fp = (fix.get("fingerprint") or fix.get("branch") or "?")[:50]
            pre = head_sha(wt)                        # the last GREEN state — exact revert target
            if not try_merge(wt, fix["branch"]):
                res.conflicts.append(fix)
                _log(f"bundle {tier} [{k}/{n}] {fp} -> conflict (excluded, kept as own branch)")
                continue
            green, detail = verify_green(cfg, wt)
            if green:
                res.included.append(fix)
                _log(f"bundle {tier} [{k}/{n}] {fp} -> green (included)")
            else:
                revert_last(wt, pre)                  # drop the fix that broke the bundle, back to GREEN
                res.pulled.append({**fix, "reason": detail})
                _log(f"bundle {tier} [{k}/{n}] {fp} -> red (pulled -> needs-human)")
        res.branch = finalize(repo, wt, f"integrate/{tier}")
        return res
    finally:
        close_bundle(repo, wt)
