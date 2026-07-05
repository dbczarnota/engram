from __future__ import annotations

from collections import Counter
from pathlib import Path

import agent as _agent
import coverage
import gitmeta
import run_coverage
import signals as _signals
from config import load_config
from fix_config import load_fix_config
from registry import parse_registry
from consolidate import consolidate
from integrate_report import render_integrate_report


def _log(msg):
    print(f"[integrate-loop] {msg}", flush=True)


def run(repo_root: Path, now: str, *, assess=_agent.assess, diffstat=gitmeta.branch_diffstat,
        branch_diff=None) -> Path:
    branch_diff = branch_diff or gitmeta.branch_diff     # late-bound so tests can monkeypatch gitmeta
    cfg = load_config(repo_root)
    registry_path = repo_root / "bug-registry.md"
    rows = parse_registry(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else []
    fixed = [r for r in rows if r.get("status") == "fixed" and r.get("branch")]

    base = gitmeta.default_base(repo_root)
    _log(f"tiering {len(fixed)} fixed branch(es); base={base}")
    decisions: list[dict] = []
    for i, r in enumerate(fixed, 1):
        branch = r["branch"]
        try:
            files, lines = diffstat(repo_root, branch, base)
            diff_text = branch_diff(repo_root, branch, base)
        except RuntimeError:
            files, lines, diff_text = [], 0, ""
        if not files:
            sig = _signals.compute_signals(r.get("dimension", ""), files, lines)
            tier = "needs-human"
            rationale = "could not compute the fix diff (branch/base?) — human review"
            decisions.append({"fingerprint": r.get("fingerprint"), "dimension": r.get("dimension"),
                              "branch": branch, "tier": tier, "rationale": rationale,
                              "signals": f"{sig.dimension_class}, {sig.files_changed}f/{sig.lines_changed}l"
                                         f"{', sensitive' if sig.sensitive else ''}"})
            _log(f"[{i}/{len(fixed)}] {(r.get('fingerprint') or '?')[:50]} -> needs-human (no computable diff)")
            continue
        sig = _signals.compute_signals(r.get("dimension", ""), files, lines)
        floor = _signals.floor_tier(sig)
        agent_tier, rationale, _tok = assess(r.get("summary", ""), r.get("dimension", ""), floor, sig,
                                             branch, repo_root, diff_text=diff_text)
        tier = _signals.clamp(floor, agent_tier)
        decisions.append({"fingerprint": r.get("fingerprint"), "dimension": r.get("dimension"),
                          "branch": branch, "tier": tier, "rationale": rationale,
                          "signals": f"{sig.dimension_class}, {sig.files_changed}f/{sig.lines_changed}l"
                                     f"{', sensitive' if sig.sensitive else ''}"})
        _log(f"[{i}/{len(fixed)}] {(r.get('fingerprint') or '?')[:50]} -> {tier} "
             f"(floor={floor}, {sig.dimension_class}, {sig.files_changed}f/{sig.lines_changed}l"
             f"{', sensitive' if sig.sensitive else ''})")

    fcfg = load_fix_config(repo_root)          # setup + verify config for the bundles
    bundles: list[dict] = []
    by_tier = {t: [d for d in decisions if d["tier"] == t] for t in ("prod-safe", "canary")}
    _log(f"consolidating bundles + full re-verify: prod-safe {len(by_tier['prod-safe'])}, "
         f"canary {len(by_tier['canary'])} candidate fix(es)")
    for tier, ds in by_tier.items():
        if not ds:
            continue
        _log(f"bundle {tier}: merging {len(ds)} fix(es) + re-verify (strong path)")
        res = consolidate(repo_root, fcfg, tier, ds)
        _log(f"bundle {tier} -> {res.branch or '(none — empty/all-pulled)'}: "
             f"included {len(res.included)}, pulled {len(res.pulled)}, conflicts {len(res.conflicts)}")
        bundles.append({"tier": tier, "branch": res.branch,
                        "included": len(res.included), "pulled": len(res.pulled),
                        "conflicts": len(res.conflicts)})
        pulled_fps = {f["fingerprint"] for f in res.pulled}
        conflict_fps = {f["fingerprint"] for f in res.conflicts}
        for d in decisions:
            if d["fingerprint"] in pulled_fps:
                d["tier"] = "needs-human"
                d["rationale"] = f"breaks the {tier} bundle — pulled for human review"
            elif d["fingerprint"] in conflict_fps:
                d["conflict"] = True
            elif res.branch and d in ds:
                d["bundle"] = res.branch

        if tier == "prod-safe" and res.branch:
            _log("prod-safe: computing line-coverage for the bundle")
            cov = run_coverage.collect_for_branch(fcfg, repo_root, res.branch)   # None if disabled/failed
            for d in [x for x in decisions if x["tier"] == "prod-safe" and x in ds]:
                if cov is None:
                    if fcfg.coverage:                        # configured but failed -> fail-safe
                        d["tier"] = "canary"
                        d["rationale"] = "coverage run failed — cannot confirm prod-safe, canary"
                        _log(f"  demote prod-safe->canary (coverage run failed): {(d.get('fingerprint') or '?')[:40]}")
                    continue
                # full (untruncated) diff — the changed-line set must be EXACT for coverage mapping
                added = coverage.added_prod_lines(
                    branch_diff(repo_root, d["branch"], "master", max_chars=10_000_000))
                if not coverage.fully_covered(added, cov):
                    d["tier"] = "canary"
                    d["rationale"] = "changed lines not covered by tests — canary"
                    _log(f"  demote prod-safe->canary (uncovered lines): {(d.get('fingerprint') or '?')[:40]}")

    report_dir = repo_root / cfg.report_dir / "integrate-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = now.replace(" ", "-").replace(":", "")
    path = report_dir / f"{stem}.md"
    path.write_text(render_integrate_report(repo_root.name, now, decisions=decisions, bundles=bundles),
                    encoding="utf-8")
    tally = Counter(d["tier"] for d in decisions)
    _log(f"done: prod-safe {tally.get('prod-safe', 0)}, canary {tally.get('canary', 0)}, "
         f"needs-human {tally.get('needs-human', 0)}; report {path.name}")
    return path
