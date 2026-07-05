from __future__ import annotations

from pathlib import Path

import rich
from baseline import run_verify_detailed as _default_vd
from richbug import _is_test_file
from triage import classify as _default_classify

_DIR = Path(__file__).resolve().parent
REPAIR_PROMPT = _DIR / "repair_prompt.md"
TEST_JUDGE_PROMPT = _DIR / "test_judge_prompt.md"
TEST_FIX_PROMPT = _DIR / "test_fix_prompt.md"

_JUDGE_SCHEMA = {"type": "object",
                 "properties": {"verdict": {"type": "string"}, "justification": {"type": "string"}},
                 "required": ["verdict", "justification"]}


def failure_set(cfg, worktree, *, run_verify_detailed=_default_vd, classify=_default_classify) -> set[str]:
    """The set of non-passing test ids right now — FAILED plus ERROR (both count against the monotonic
    gate; only FAILED are repair targets, but a new ERROR is still a regression)."""
    tr = classify(run_verify_detailed(cfg, worktree))
    return {f.id for f in tr.failures} | set(tr.errors)


def repair_gate(cfg, worktree, target_id, baseline_ids, changed, *, baseline_env_cmds=frozenset(),
                run_verify_detailed=_default_vd, classify=_default_classify) -> tuple[bool, str]:
    from gate import blast_radius_ok
    ok, why = blast_radius_ok(changed)
    if not ok:
        return (False, f"blast-radius: {why}")
    tr = classify(run_verify_detailed(cfg, worktree))
    now = {f.id for f in tr.failures} | set(tr.errors)   # FAILED + ERROR: a new ERROR is a regression too
    if target_id in now:
        return (False, f"target still failing: {target_id}")
    new = now - (set(baseline_ids) - {target_id})
    if new:
        return (False, f"introduced new failure(s): {sorted(new)}")
    # A fix that turns a previously-runnable command un-runnable (e.g. a syntax/import error that breaks
    # pytest collection) makes its failures VANISH from `now` — which would otherwise read as "green".
    # Reject: an empty failure set that was bought by breaking a command is a regression, not a repair.
    broke = tr.env_commands - set(baseline_env_cmds)
    if broke:
        return (False, f"fix broke a command (now un-runnable): {sorted(broke)}")
    return (True, "gate passed")


def repair_impl(finding, plan: dict, worktree: Path, feedback: str = "") -> tuple[str, str, int]:
    """Mirrors rich.run_impl's (finding, plan, worktree, feedback) -> (status, self_critique, tokens)
    shape, but reads repair_prompt.md (code-only repair) instead of rich_impl_prompt.md (behavior-
    preserving refactor), and disallows Bash the same way."""
    import rich

    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (REPAIR_PROMPT.read_text(encoding="utf-8")
            .replace("{ID}", str(plan.get("id", "")))
            .replace("{COMMAND}", str(plan.get("command", "")))
            .replace("{SNIPPET}", str(plan.get("snippet", "")))
            .replace("{FEEDBACK}", feedback or "(none)"))
    (prompt_dir / "repair.md").write_text(text, encoding="utf-8")
    so, tokens, status = rich._run_claude(worktree, "repair.md", rich.IMPL_SCHEMA,
                                          "Read,Grep,Glob,Edit,Write", "Bash")
    if status != "ok":
        return (status, "", tokens)
    return (("applied" if so.get("applied") else "no-op"), str(so.get("self_critique") or ""), tokens)


def _run_impl(failure, worktree, feedback, impl_agent):
    """Adapt rich.run_impl's (finding, plan, worktree, feedback) shape to a repair failure. The 'plan'
    carries the failure id/command/snippet so repair_prompt.md can be filled."""
    plan = {"root_cause": failure.snippet, "approach": f"fix {failure.id}",
            "justification": failure.command, "id": failure.id, "command": failure.command,
            "snippet": failure.snippet}

    class _F:  # minimal finding shim: run_impl reads .dimension/.file/.summary
        dimension = "baseline-repair"
        file = failure.file
        summary = failure.snippet
    return impl_agent(_F(), plan, worktree, feedback)


def run_repair_fix(cfg, worktree, failure, baseline_ids, *, impl_agent=repair_impl,
                   baseline_env_cmds=frozenset(),
                   run_verify_detailed=_default_vd, classify=_default_classify,
                   max_retries: int = 2) -> tuple[str, int, str]:
    """Code-only rich repair of one already-RED baseline failure. On 'fixed', the code edit is LEFT
    uncommitted for the caller to commit+branch. Every non-fixed exit resets the worktree to master."""
    import gitops
    cost = 0
    feedback = ""
    for _attempt in range(max_retries + 1):
        status, _critique, tok = _run_impl(failure, worktree, feedback, impl_agent)
        cost += tok
        if status == "rate-limited":
            gitops.reset_hard_master(worktree)
            return ("rate-limited", cost, "impl rate-limited")
        if status != "applied" or gitops.suite_is_clean(worktree):
            gitops.reset_hard_master(worktree)
            feedback = "no production change was applied; fix the code so the failing check passes"
            continue
        changed = gitops.changed_files(worktree)
        if any(_is_test_file(f) for f in changed):
            gitops.reset_hard_master(worktree)
            feedback = "you edited a test; fix the PRODUCTION code only — the test must not change"
            continue
        ok, reason = repair_gate(cfg, worktree, failure.id, baseline_ids, changed,
                                 baseline_env_cmds=baseline_env_cmds,
                                 run_verify_detailed=run_verify_detailed, classify=classify)
        if ok:
            return ("fixed", cost, "gate passed")     # leave the edit for the caller to commit
        gitops.reset_hard_master(worktree)
        feedback = f"the gate rejected your fix: {reason}. Address exactly that; fix code only."
    return ("needs-human", cost, f"exhausted {max_retries} retries: {feedback}")


def judge_test_wrong(failure, worktree) -> tuple[str, str, int]:
    """Independent, read-only adversary: does the failing test encode the WRONG expected behaviour? Biased
    against 'test-wrong'; fails CLOSED to 'test-ok' on any non-ok claude status so an errored judge never
    licenses a test change."""
    prompt_dir = worktree / ".fl"; prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (TEST_JUDGE_PROMPT.read_text(encoding="utf-8")
            .replace("{ID}", failure.id).replace("{COMMAND}", failure.command)
            .replace("{SNIPPET}", failure.snippet))
    (prompt_dir / "testjudge.md").write_text(text, encoding="utf-8")
    so, tokens, status = rich._run_claude(worktree, "testjudge.md", _JUDGE_SCHEMA,
                                          "Read,Grep,Glob", "Edit,Write,Bash")
    if status != "ok":
        return ("test-ok", f"judge {status}", tokens)      # fail-closed
    verdict = str(so.get("verdict") or "").strip().lower()
    return (("test-wrong" if verdict == "test-wrong" else "test-ok"),
            str(so.get("justification") or "").strip(), tokens)


def fix_test(failure, justification: str, worktree, feedback: str = "") -> tuple[str, str, int]:
    """Edits ONLY the failing test file to correct its expectation. Never touches production code."""
    prompt_dir = worktree / ".fl"; prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (TEST_FIX_PROMPT.read_text(encoding="utf-8")
            .replace("{ID}", failure.id).replace("{COMMAND}", failure.command)
            .replace("{SNIPPET}", failure.snippet).replace("{JUSTIFICATION}", justification or "")
            .replace("{FEEDBACK}", feedback or "(none)"))
    (prompt_dir / "testfix.md").write_text(text, encoding="utf-8")
    so, tokens, status = rich._run_claude(worktree, "testfix.md", rich.IMPL_SCHEMA,
                                          "Read,Grep,Glob,Edit,Write", "Bash")
    if status != "ok":
        return (status, "", tokens)
    return (("applied" if so.get("applied") else "no-op"), str(so.get("self_critique") or ""), tokens)


def run_repair_with_exception(cfg, worktree, failure, baseline_ids, *, impl_agent=None,
                              baseline_env_cmds=frozenset(),
                              judge=judge_test_wrong, test_fixer=fix_test,
                              run_verify_detailed=_default_vd, classify=_default_classify,
                              max_retries: int = 2) -> tuple[str, int, str]:
    """Code-first repair (Plan A); on needs-human, consult the adversarial judge and, only if it rules the
    test wrong, produce a human-gated test-change branch (outcome 'proposed-test'). Never a silent fix."""
    import gitops
    kw = {} if impl_agent is None else {"impl_agent": impl_agent}
    outcome, cost, reason = run_repair_fix(cfg, worktree, failure, baseline_ids,
                                           baseline_env_cmds=baseline_env_cmds,
                                           run_verify_detailed=run_verify_detailed, classify=classify,
                                           max_retries=max_retries, **kw)
    if outcome != "needs-human":
        return (outcome, cost, reason)

    gitops.reset_hard_master(worktree)
    verdict, justification, tok = judge(failure, worktree)
    cost += tok
    if verdict != "test-wrong":
        return ("needs-human", cost, reason)

    feedback = ""
    for _attempt in range(max_retries + 1):
        status, _crit, tok = test_fixer(failure, justification, worktree, feedback)
        cost += tok
        if status == "rate-limited":
            gitops.reset_hard_master(worktree)
            return ("rate-limited", cost, "test-fix rate-limited")
        if status != "applied" or gitops.suite_is_clean(worktree):
            gitops.reset_hard_master(worktree)
            feedback = "no change was applied; correct the test's expectation"
            continue
        changed = gitops.changed_files(worktree)
        if any(not _is_test_file(f) for f in changed):
            gitops.reset_hard_master(worktree)
            feedback = "you touched non-test code; correct ONLY the failing test file"
            continue
        ok, greason = repair_gate(cfg, worktree, failure.id, baseline_ids, changed,
                                  baseline_env_cmds=baseline_env_cmds,
                                  run_verify_detailed=run_verify_detailed, classify=classify)
        if ok:
            return ("proposed-test", cost, f"test-is-wrong: {justification}")   # leave edit for caller
        gitops.reset_hard_master(worktree)
        feedback = f"the gate rejected the change: {greason}. Correct the test precisely."
    return ("needs-human", cost, f"test-is-wrong but no coherent correction: {justification}")
