from __future__ import annotations

import hashlib
import os
from pathlib import Path

import baseline
import gitops
from backlog import dedup_key, select_fixes, set_status
from dossier import write_dossier
from fix_config import load_fix_config
from fixer import run_fixer, skeptic_check
from gate import gate_fix
from rich import run_rich_refactor
from richbug import run_rich_bug
from registry import parse_registry, render_registry
from fix_report import render_fix_report
from repair import run_repair_with_exception
from triage import classify as _triage_classify, is_pre_flight_blocked
from verify import run_verify as _default_verify
from worktree import create_worktree as _default_create, remove_worktree as _default_remove


def _log(msg):
    print(f"[fix-loop] {msg}", flush=True)


def _fix_branch(finding) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in finding.fingerprint)[:30].strip("-")
    # append a hash of the FULL fingerprint so two findings sharing a 30-char prefix don't collide
    # (git branch -f would silently overwrite the earlier fix branch).
    h = hashlib.sha1(finding.fingerprint.encode("utf-8")).hexdigest()[:8]
    return f"fix/{slug}-{h}"


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _recover(rows):
    """Reset any leftover `in-progress` -> `pending`. A hard kill (power loss, SIGKILL) can strand a row
    mid-flight; on the next run those must be re-attempted, not skipped. Pure — returns new rows."""
    return [({**r, "status": "pending"} if r.get("status") == "in-progress" else r) for r in rows]


def _persist(registry_path: Path, rows) -> None:
    """Atomically write the backlog with in-progress reset to pending. Called after EACH candidate
    (incremental durability: a crash loses at most the one in-flight fix, never the whole run) and once
    more in the finally. Atomic tmp+os.replace means a crash mid-write never corrupts the registry."""
    _atomic_write(registry_path, render_registry(_recover(rows)))


def _subsume_siblings(rows, candidates, fixed_finding, branch, subsumed_fps, subsumed):
    """After a fix lands, mark still-open candidates sharing its (file, symbol, dimension) as `subsumed`
    — one fix over a function covers sibling issues there, so the loop never produces a second overlapping
    branch nor surfaces redundant work to the human. Outcome-aware: called ONLY after a success."""
    key = dedup_key({"fingerprint": fixed_finding.fingerprint, "dimension": fixed_finding.dimension})
    if key is None:
        return rows
    _terminal = {"fixed", "failed", "needs-human", "deferred", "subsumed"}
    for c in candidates:
        fp = c.get("fingerprint")
        if not fp or fp == fixed_finding.fingerprint or fp in subsumed_fps:
            continue
        current = next((r for r in rows if r.get("fingerprint") == fp), None)
        if current is not None and current.get("status") in _terminal:
            continue   # already handled this run — never clobber a fixed/failed row
        if dedup_key(c) == key:
            subsumed_fps.add(fp)
            rows = set_status(rows, fp, "subsumed", subsumed_by=branch)
            subsumed.append({"fingerprint": fp, "dimension": c.get("dimension", ""),
                             "summary": c.get("summary", ""), "subsumed_by": branch})
            _log(f"  subsumes {fp}")
    return rows


def _repair_finding_shim(failure):
    """Adapt a triage.Failure to the minimal shape `_fix_branch` needs (reads `.fingerprint`)."""
    class _S:
        fingerprint = failure.id
    return _S()


def run(repo_root: Path, now: str, *, fixer=run_fixer, skeptic=skeptic_check,
        run_verify=_default_verify, create_worktree=_default_create, remove_worktree=_default_remove,
        max_fixes: int | None = None) -> Path:
    from report import Finding  # review-loop Finding
    cfg = load_fix_config(repo_root)
    # Resolve capability-variant verify commands (full pytest+testcontainers WITH Docker, else the
    # `not requires_docker` slice) once, up front — strong path by default, graceful fallback if the
    # Docker daemon is unreachable.
    _docker = baseline.docker_available()
    cfg.verify = baseline.resolve_verify(cfg.verify, docker_available=_docker)
    _log(f"verify: {'strong path (Docker up)' if _docker else 'light path (no Docker)'} — {list(cfg.verify)}")
    dossier_dir = repo_root / cfg.report_dir / "needs-human"   # one hand-off note per deferred finding
    registry_path = repo_root / "bug-registry.md"
    rows = parse_registry(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else []
    rows = _recover(rows)   # startup recovery: a prior hard kill may have stranded in-progress rows
    candidates = select_fixes(rows, fix_classes=("refactor", "bug"))

    fixed: list = []
    failed: list = []
    deferred: list = []
    repaired: list = []
    repair_needs_human: list = []
    blocked_env: list = []
    subsumed: list = []           # findings covered by a sibling fix (same file:symbol:dimension)
    subsumed_fps: set = set()     # their fingerprints — skipped in the candidate loop, never re-fixed
    spent = 0
    stop_reason = "no-pending"
    branch = "fl/" + now.replace(" ", "-").replace(":", "")
    worktree = create_worktree(repo_root, branch)
    _log(f"worktree ready; {len(candidates)} registry candidate(s)")
    gitops.ensure_scratch(worktree)
    try:
        # Bootstrap the worktree environment (e.g. `uv sync` to create `.venv`) BEFORE verify — a bare
        # git worktree has no deps, so pyright/pytest would fail for environment reasons and every run
        # would misread as blocked-environment. If setup fails we cannot trust any verify, so do nothing.
        setup_ok, setup_detail = baseline.run_setup(cfg, worktree)
        _log("setup: ok" if setup_ok else f"setup FAILED: {setup_detail[:100]}")
        if not setup_ok:
            stop_reason = "setup-failed"
            blocked_env = [f"setup failed: {setup_detail}"]
            candidates = []
        # Baseline gate: the suite must be green on master before any fix. Always the REAL
        # structured verify (not the injected `run_verify`, which gates individual post-fix diffs).
        # A red baseline no longer aborts the run outright — genuine failures are triaged and
        # repaired (code-only, monotonic gate) before registry findings are attempted.
        results = baseline.run_verify_detailed(cfg, worktree) if setup_ok else []
        tr = _triage_classify(results)
        if setup_ok:
            blocked_env = list(tr.blocked_env)
        if setup_ok:
            if is_pre_flight_blocked(tr):
                _log(f"baseline: blocked-environment ({len(tr.blocked_env)} cmd)")
            elif tr.failures:
                _log(f"baseline RED: {len(tr.failures)} failures, {len(tr.env_commands)} env-blocked -> repair mode")
            else:
                _log("baseline: green")
        if setup_ok and is_pre_flight_blocked(tr):
            stop_reason = "blocked-environment"
            candidates = []
        elif setup_ok and tr.failures:
            baseline_ids = {f.id for f in tr.failures} | set(tr.errors)   # FAILED + ERROR at baseline
            baseline_env_cmds = set(tr.env_commands)   # commands already un-runnable at baseline
            repair_interrupted = False
            for i, failure in enumerate(tr.failures, 1):
                if spent >= cfg.budget_tokens:
                    stop_reason = "budget"
                    repair_interrupted = True
                    break
                _log(f"repair {i}/{len(tr.failures)}: {failure.id}")
                gitops.checkout_master(worktree)
                outcome, cost, reason = run_repair_with_exception(
                    cfg, worktree, failure, baseline_ids, baseline_env_cmds=baseline_env_cmds)
                spent += cost
                _log(f"  -> {outcome} ({cost} tok, spent {spent})")
                if outcome == "rate-limited":
                    stop_reason = "rate-limited"
                    repair_interrupted = True
                    gitops.reset_hard_master(worktree)
                    break
                if outcome == "fixed":
                    fb = _fix_branch(_repair_finding_shim(failure))
                    gitops.commit_and_branch(worktree, f"fix(baseline-repair): {failure.id[:60]}", fb)
                    repaired.append({"id": failure.id, "branch": fb, "cost": str(cost)})
                elif outcome == "proposed-test":
                    fb = _fix_branch(_repair_finding_shim(failure))
                    gitops.commit_and_branch(
                        worktree, f"test(baseline-repair): PROPOSED {failure.id[:50]}", fb)
                    repair_needs_human.append({"id": failure.id, "reason": reason,
                                               "branch": fb, "kind": "proposed-test-change"})
                else:  # needs-human
                    repair_needs_human.append({"id": failure.id, "reason": reason})
            # re-evaluate once: only proceed to registry findings if the repair pass ran to
            # completion (not budget/rate-limited) AND the baseline is now fully green.
            if repair_interrupted:
                candidates = []
            else:
                post = _triage_classify(baseline.run_verify_detailed(cfg, worktree))
                # "fully green" requires NO genuine failures AND NO un-runnable command — a command that
                # cannot run (e.g. env-blocked pytest) means the suite is not trustworthy, so registry
                # findings stay deferred rather than being fixed against an unverifiable baseline.
                if post.failures or post.env_commands or post.errors:
                    stop_reason = "baseline-repair"
                    candidates = []
                # else: green -> fall through to the existing candidate loop below
        # else: baseline green -> candidates already selected; proceed unchanged
        for k, row in enumerate(candidates, 1):
            _persist(registry_path, rows)   # durable checkpoint: prior candidates' results are on disk
            if row["fingerprint"] in subsumed_fps:
                _log(f"[{k}/{len(candidates)}] {row['fingerprint']} -> subsumed (a sibling fix covers it)")
                continue
            if max_fixes is not None and len(fixed) + len(failed) >= max_fixes:
                stop_reason = "max-fixes"
                break
            if spent >= cfg.budget_tokens:
                stop_reason = "budget"
                break
            finding = Finding(fingerprint=row["fingerprint"], file=row.get("file", ""), line=None,
                              dimension=row.get("dimension", ""), severity=row.get("severity", ""),
                              layer="", summary=row.get("summary", ""))
            _log(f"[{k}/{len(candidates)}] {finding.fingerprint} ({row.get('fix_class', '?')})")
            rows = set_status(rows, finding.fingerprint, "in-progress")
            try:
                if row.get("fix_class") == "bug":
                    # bug-class → RICH-BUG (test->RED->fix->GREEN). run_rich_bug does its own
                    # checkout_master, commits the regression test, and (on 'fixed') leaves the fix
                    # uncommitted on top for us to commit+branch — master -> test commit -> fix commit.
                    b_outcome, b_plan, bcost, b_reason = run_rich_bug(
                        cfg, worktree, finding, run_verify=run_verify)
                    spent += bcost
                    if b_outcome == "rate-limited":
                        rows = set_status(rows, finding.fingerprint, "deferred")
                        deferred.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                                         "summary": finding.summary})
                        stop_reason = "rate-limited"
                        gitops.reset_hard_master(worktree)
                        break
                    if b_outcome == "fixed":
                        fb = _fix_branch(finding)
                        gitops.commit_and_branch(
                            worktree, f"fix({finding.dimension}): {finding.summary[:60]}", fb)
                        rows = set_status(rows, finding.fingerprint, "fixed", branch=fb, cost=bcost,
                                          attempts=int(row.get("attempts") or 0) + 1)
                        fixed.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                                      "summary": finding.summary, "branch": fb, "cost": str(bcost)})
                        rows = _subsume_siblings(rows, candidates, finding, fb, subsumed_fps, subsumed)
                    else:  # needs-human
                        rows = _fail(rows, failed, finding, f"rich-bug: {b_reason}",
                                     attempts=int(row.get("attempts") or 0) + 1)
                        _wip = gitops.wip_branch(finding.fingerprint)
                        _wip = _wip if gitops.branch_exists(worktree, _wip) else None
                        failed[-1]["dossier"] = str(
                            write_dossier(dossier_dir, finding, b_reason, b_plan, wip=_wip))
                    _log(f"  -> {b_outcome} ({bcost} tok, spent {spent})")
                    continue
                gitops.checkout_master(worktree)
                outcome, tok = fixer(finding, worktree)
                spent += tok
                if outcome == "rate-limited":
                    rows = set_status(rows, finding.fingerprint, "deferred")
                    deferred.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                                     "summary": finding.summary})
                    stop_reason = "rate-limited"
                    gitops.reset_hard_master(worktree)
                    break
                if tok > cfg.per_fix_cap:
                    # a single runaway fix must not be trusted or repeated
                    gitops.reset_hard_master(worktree)
                    rows = _fail(rows, failed, finding, f"too-expensive ({tok} > {cfg.per_fix_cap})",
                                 attempts=int(row.get("attempts") or 0) + 1)
                    continue
                if outcome != "applied" or gitops.suite_is_clean(worktree):
                    gitops.reset_hard_master(worktree)
                    rows = _fail(rows, failed, finding, "no change applied",
                                 attempts=int(row.get("attempts") or 0) + 1)
                    continue
                changed = gitops.changed_files(worktree)
                ok, why, sk_tok = gate_fix(cfg, worktree, finding, changed, run_verify=run_verify,
                                           skeptic=skeptic)
                spent += sk_tok
                if not ok:
                    # escalate the failed one-shot refactor to the rich process (plan + implement +
                    # self-critique + gate + targeted retry) — still suite-green, no red->green here.
                    gitops.reset_hard_master(worktree)
                    r_outcome, r_plan, rcost, r_reason = run_rich_refactor(
                        cfg, worktree, finding, run_verify=run_verify)
                    spent += rcost
                    if r_outcome == "rate-limited":
                        rows = set_status(rows, finding.fingerprint, "deferred")
                        deferred.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                                         "summary": finding.summary})
                        stop_reason = "rate-limited"
                        gitops.reset_hard_master(worktree)
                        break
                    if r_outcome == "fixed":
                        fb = _fix_branch(finding)
                        gitops.commit_and_branch(
                            worktree, f"fix({finding.dimension}): {finding.summary[:60]}", fb)
                        # cost = one-shot fixer (tok) + one-shot gate skeptic (sk_tok) + rich turns (rcost)
                        fix_cost = tok + sk_tok + rcost
                        rows = set_status(rows, finding.fingerprint, "fixed", branch=fb, cost=fix_cost,
                                          attempts=int(row.get("attempts") or 0) + 1)
                        fixed.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                                      "summary": finding.summary, "branch": fb, "cost": str(fix_cost)})
                        rows = _subsume_siblings(rows, candidates, finding, fb, subsumed_fps, subsumed)
                    else:  # needs-human
                        rows = _fail(rows, failed, finding, f"rich: {r_reason}",
                                     attempts=int(row.get("attempts") or 0) + 1)
                        _wip = gitops.wip_branch(finding.fingerprint)
                        _wip = _wip if gitops.branch_exists(worktree, _wip) else None
                        failed[-1]["dossier"] = str(
                            write_dossier(dossier_dir, finding, r_reason, r_plan, wip=_wip))
                    _log(f"  -> {r_outcome} ({rcost} tok, spent {spent})")
                    continue
                fb = _fix_branch(finding)
                sha = gitops.commit_and_branch(worktree,
                                               f"fix({finding.dimension}): {finding.summary[:60]}", fb)
                rows = set_status(rows, finding.fingerprint, "fixed", branch=fb, cost=tok,
                                  attempts=int(row.get("attempts") or 0) + 1)
                fixed.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                              "summary": finding.summary, "branch": fb, "cost": str(tok)})
                rows = _subsume_siblings(rows, candidates, finding, fb, subsumed_fps, subsumed)
                _log(f"  -> fixed ({tok} tok, spent {spent})")
            except Exception as e:
                # per-candidate isolation: a crash on ONE finding (git error, agent glitch, IO) must not
                # abort the whole run. Reset to a clean tree, mark it failed, keep going. The registry is
                # persisted at the top of the next iteration, so progress survives.
                try:
                    gitops.reset_hard_master(worktree)
                except Exception:
                    pass
                rows = _fail(rows, failed, finding, f"exception: {type(e).__name__}: {e}"[:200],
                             attempts=int(row.get("attempts") or 0) + 1)
                _log(f"  -> exception ({type(e).__name__}) — marked failed, continuing")
                continue
        _log(f"stop: {stop_reason} | repaired {len(repaired)} fixed {len(fixed)} "
             f"needs-human {len(repair_needs_human) + len(failed)} deferred {len(deferred)} | "
             f"spent {spent}/{cfg.budget_tokens}")
    finally:
        remove_worktree(repo_root, worktree)
        # Always persist the backlog (resumability), even if the loop raised.
        _persist(registry_path, rows)

    report_dir = repo_root / cfg.report_dir / "fix-loop-reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = now.replace(" ", "-").replace(":", "")
    report_path = report_dir / f"{stem}.md"
    report_path.write_text(render_fix_report(
        repo_root.name, now, fixed=fixed, failed=failed, deferred=deferred,
        budget_spent=spent, budget_total=cfg.budget_tokens, stop_reason=stop_reason,
        repaired=repaired, repair_needs_human=repair_needs_human, blocked_env=blocked_env,
        subsumed=subsumed),
        encoding="utf-8")
    return report_path


def _fail(rows, failed, finding, reason, *, attempts):
    status = "needs-human" if attempts >= 3 else "failed"
    failed.append({"fingerprint": finding.fingerprint, "dimension": finding.dimension,
                   "summary": finding.summary, "reason": reason})
    return set_status(rows, finding.fingerprint, status, attempts=attempts)


def _report_stop_reason(report_path: Path) -> str:
    """Read the stop_reason out of a fix-loop report's frontmatter (single source of truth for why a
    run() ended). Returns 'unknown' if the report is unreadable or malformed."""
    try:
        for line in report_path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("stop_reason:"):
                return s.split(":", 1)[1].strip().strip("*").strip()
    except OSError:
        pass
    return "unknown"


def _open_candidates(repo_root: Path) -> int:
    """How many pending refactor/bug candidates remain — the loop's own view (select_fixes), so
    unselectable pending rows never make the driver think there's work left."""
    p = repo_root / "bug-registry.md"
    if not p.is_file():
        return 0
    rows = parse_registry(p.read_text(encoding="utf-8", errors="replace"))
    return len(select_fixes(rows, fix_classes=("refactor", "bug")))


# stop_reasons that mean "the environment/baseline is broken" — waiting/retrying won't help this run.
_FATAL_STOPS = frozenset({"blocked-environment", "setup-failed", "baseline-repair"})
# stop_reasons (or a raised run()) that are transient — cool down, then resume from the durable registry.
_TRANSIENT_STOPS = frozenset({"rate-limited", "error"})


def run_until_done(repo_root: Path, *, max_seconds: int = 9 * 3600, cooldown_s: int = 1800,
                   max_stuck: int = 5, run=run, open_candidates=_open_candidates,
                   nowfn=None, sleep=None, clock=None) -> str:
    """Resilient driver: run() the fix-loop repeatedly until the bucket is empty or the deadline, RESUMING
    after ANY interruption — a rate-limit, a raised exception (network/git/OS), or a per-run budget stop.
    Durability lives in the registry (run() persists after every candidate + recovers stranded rows on
    start), so this is also safe to relaunch after a hard kill / power loss: it picks up where it left off.

    Returns why it stopped: 'done' | 'deadline' | 'stuck' | a fatal stop_reason. Everything is injectable
    (run/open_candidates/nowfn/sleep/clock) so it is unit-testable without a real repo or claude."""
    import time as _time
    nowfn = nowfn or (lambda: _time.strftime("%Y-%m-%d %H%M"))
    sleep = sleep or _time.sleep
    clock = clock or _time.monotonic

    deadline = clock() + max_seconds
    stuck = 0
    it = 0
    while True:
        if clock() >= deadline:
            _log("run_until_done: deadline reached — stopping")
            return "deadline"
        if open_candidates(repo_root) == 0:
            _log("run_until_done: no open candidates — DONE")
            return "done"
        before = open_candidates(repo_root)
        it += 1
        try:
            reason = _report_stop_reason(run(repo_root, nowfn()))
            _log(f"run_until_done: iter {it} stop_reason={reason}")
        except Exception as e:                       # any crash: network, git, OOM, whatever
            reason = "error"
            _log(f"run_until_done: iter {it} run() raised {type(e).__name__}: {e}")
        if reason == "no-pending":
            _log("run_until_done: bucket empty — DONE")
            return "done"
        if reason in _FATAL_STOPS:
            _log(f"run_until_done: environment/baseline problem ({reason}) — stopping for a human")
            return reason
        # progress guard: if a run resolved nothing (persistent rate-limit/error), don't spin forever.
        if open_candidates(repo_root) < before:
            stuck = 0
        else:
            stuck += 1
            if stuck >= max_stuck:
                _log(f"run_until_done: {stuck} iters with no progress ({reason}) — stopping")
                return "stuck"
        wait = cooldown_s if reason in _TRANSIENT_STOPS else 2   # budget resets per run(): resume quickly
        if wait >= deadline - clock():
            _log("run_until_done: not enough time left for cooldown — stopping")
            return "deadline"
        _log(f"run_until_done: {reason} — cooldown {wait}s then resume")
        sleep(wait)
