from __future__ import annotations

from pathlib import Path

import rich   # reuse _run_claude, schemas, and the claude-invocation pattern

_DIR = Path(__file__).resolve().parent
TEST_PROMPT = _DIR / "richbug_test_prompt.md"
IMPL_PROMPT = _DIR / "richbug_impl_prompt.md"


def _is_test_file(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    base = p.rsplit("/", 1)[-1]
    if not base.endswith(".py"):
        return False
    return ("/tests/" in p or p.startswith("tests/") or base.startswith("test_")
            or base.endswith("_test.py") or base == "conftest.py")


def run_test_turn(finding, worktree: Path) -> tuple[dict, int, str]:
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (TEST_PROMPT.read_text(encoding="utf-8")
            .replace("{DIMENSION}", finding.dimension).replace("{FILE}", finding.file)
            .replace("{SUMMARY}", finding.summary))
    (prompt_dir / "test.md").write_text(text, encoding="utf-8")
    return rich._run_claude(worktree, "test.md", rich.PLAN_SCHEMA, "Read,Grep,Glob,Edit,Write", "Bash")


def run_bug_impl(finding, plan: dict, worktree: Path, feedback: str = "") -> tuple[str, str, int]:
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (IMPL_PROMPT.read_text(encoding="utf-8")
            .replace("{DIMENSION}", finding.dimension).replace("{FILE}", finding.file)
            .replace("{SUMMARY}", finding.summary)
            .replace("{ROOT_CAUSE}", str(plan.get("root_cause", "")))
            .replace("{APPROACH}", str(plan.get("approach", "")))
            .replace("{JUSTIFICATION}", str(plan.get("justification", "")))
            .replace("{FEEDBACK}", feedback or "(none)"))
    (prompt_dir / "bugimpl.md").write_text(text, encoding="utf-8")
    so, tokens, status = rich._run_claude(worktree, "bugimpl.md", rich.IMPL_SCHEMA,
                                          "Read,Grep,Glob,Edit,Write", "Bash")
    if status != "ok":
        return (status, "", tokens)
    return (("applied" if so.get("applied") else "no-op"), str(so.get("self_critique") or ""), tokens)


def _bug_skeptic(finding, plan: dict, worktree: Path) -> tuple[str, str, int]:
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt = (f"A bug fix (plus a regression test) was applied for: dimension={finding.dimension}, "
              f"file={finding.file}, claim={finding.summary}. The author's plan was: "
              f"approach={plan.get('approach')}, justification={plan.get('justification')}. Read the "
              f"CURRENT code (with the fix) and the regression test. Decide whether the fix genuinely "
              f"resolves the bug (the regression test truly exercises it and now passes) AND matches the "
              f"plan WITHOUT introducing a new problem or weakening the test. Return verdict 'refuted' "
              f"ONLY if it does not; otherwise 'confirmed'.")
    (prompt_dir / "bugcheck.md").write_text(prompt, encoding="utf-8")
    so, tokens, status = rich._run_claude(worktree, "bugcheck.md", rich.SKEPTIC_SCHEMA,
                                          "Read,Grep,Glob", "Edit,Write,Bash")
    if status != "ok":
        return ("confirmed", f"skeptic {status}", tokens)
    verdict = str(so.get("verdict") or "").strip().lower()
    return (("refuted" if verdict == "refuted" else "confirmed"), str(so.get("reason") or "").strip(), tokens)


def run_rich_bug(cfg, worktree, finding, *, run_verify, test_agent=run_test_turn,
                 impl_agent=run_bug_impl, skeptic=_bug_skeptic,
                 max_retries: int = 2) -> tuple[str, dict, int, str]:
    """Two-phase test->RED->fix->GREEN. Turn 1 writes ONLY a test; the orchestrator commits it (test_sha)
    and proves the suite RED; Turn 2 implements the fix on top; gate_fix (blast-radius + full suite GREEN
    + bug-skeptic) verifies. Gate failure resets to test_sha (keeping the proven test) and re-runs Turn 2.
    On 'fixed' the test is committed and the fix is left uncommitted for the caller to commit+branch."""
    import gitops
    from gate import gate_fix

    cost = 0
    gitops.checkout_master(worktree)                 # clean, detached at master
    gitops.ensure_scratch(worktree)                  # keep .fl/ gitignored so it never trips the
                                                     # test-only check nor inflates changed_files
    plan, tok, status = test_agent(finding, worktree)
    cost += tok
    if status == "rate-limited":
        gitops.reset_hard_master(worktree)
        return ("rate-limited", plan, cost, "test-turn rate-limited")
    if status != "ok":
        gitops.reset_hard_master(worktree)
        return ("needs-human", plan, cost, "no usable test/plan produced")

    changed = gitops.changed_files(worktree)
    if not changed or any(not _is_test_file(f) for f in changed):
        gitops.reset_hard_master(worktree)
        return ("needs-human", plan, cost, f"turn 1 must write only a test (changed: {changed})")

    test_sha = gitops.commit_wip(worktree, f"test({finding.dimension}): regression for {finding.summary[:50]}")
    red_passed, _detail = run_verify(cfg, worktree)   # suite WITH the test, no fix
    if red_passed:                                    # green => the test does not reproduce the bug
        gitops.reset_hard_master(worktree)
        return ("needs-human", plan, cost, "test-not-reproducing (suite green without a fix)")

    feedback = ""
    for _attempt in range(max_retries + 1):
        status, _critique, tok = impl_agent(finding, plan, worktree, feedback)
        cost += tok
        if status == "rate-limited":
            gitops.reset_hard_master(worktree)
            return ("rate-limited", plan, cost, "implement rate-limited")
        if status != "applied" or gitops.suite_is_clean(worktree):
            gitops.reset_hard(worktree, test_sha)     # keep the test, drop any partial fix
            feedback = "your previous attempt made no production change; implement the fix so the test passes"
            continue
        changed = gitops.changed_files(worktree)      # the fix's files (test already committed)
        if any(_is_test_file(f) for f in changed):
            gitops.reset_hard(worktree, test_sha)      # the fix must not touch the proven regression test
            feedback = "your fix modified or deleted the regression test; fix ONLY production code"
            continue
        ok, reason, sk_tok = gate_fix(cfg, worktree, finding, changed, run_verify=run_verify,
                                      skeptic=lambda f, w: skeptic(f, plan, w))
        cost += sk_tok
        if ok:
            return ("fixed", plan, cost, "gate passed")     # test committed; fix left for the caller
        if _attempt == max_retries:
            # last attempt failed the gate — preserve BOTH the regression test and the fix attempt on a
            # wip branch (master -> test_sha -> fix) for the human before cleaning.
            gitops.commit_and_branch(worktree, f"wip(needs-human): {finding.fingerprint[:50]}",
                                     gitops.wip_branch(finding.fingerprint))
            gitops.reset_hard_master(worktree)
            return ("needs-human", plan, cost, f"exhausted {max_retries} retries: {reason}")
        gitops.reset_hard(worktree, test_sha)         # discard the fix, KEEP the proven test
        feedback = f"the gate rejected your fix: {reason}. Address exactly that and re-implement."
    gitops.reset_hard_master(worktree)                # discard the test commit too
    return ("needs-human", plan, cost, f"exhausted {max_retries} retries: {feedback}")
