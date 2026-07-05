from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from claude_iterate import _claude_exe, _parse_envelope, classify_outcome

_DIR = Path(__file__).resolve().parent
PLAN_PROMPT = _DIR / "rich_plan_prompt.md"
IMPL_PROMPT = _DIR / "rich_impl_prompt.md"

# Per-call hard cap on a nested `claude -p` turn. WITHOUT this, a rate-limited/stuck call blocks
# subprocess.run indefinitely (observed: one call froze a run for ~3h waiting out a rate-limit window),
# which is fatal for an autonomous nightly loop. On timeout we treat it as rate-limited so the loop
# defers gracefully and stops (resume next run) instead of hanging. Generous enough for a real turn.
_CLAUDE_TIMEOUT_S = 600

PLAN_SCHEMA: dict = {
    "type": "object",
    "properties": {"root_cause": {"type": "string"}, "approach": {"type": "string"},
                   "alternatives": {"type": "string"}, "justification": {"type": "string"}},
    "required": ["root_cause", "approach", "justification"],
}
IMPL_SCHEMA: dict = {
    "type": "object",
    "properties": {"applied": {"type": "boolean"}, "self_critique": {"type": "string"}},
    "required": ["applied", "self_critique"],
}
SKEPTIC_SCHEMA: dict = {
    "type": "object",
    "properties": {"verdict": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["verdict", "reason"],
}


def _out_tokens(env: dict) -> int:
    try:
        return int((env.get("usage") or {}).get("output_tokens") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def _run_claude(worktree: Path, prompt_file: str, schema: dict, allowed: str,
                disallowed: str) -> tuple[dict, int, str]:
    """Run one claude -p turn against a prompt file already written under .fl/. Returns
    (structured_output, tokens, status) where status in {ok, rate-limited, error}."""
    short = (f"Read the file .fl/{prompt_file} relative to the current working directory and follow it "
             "exactly, then return the object.")
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short,
             "--output-format", "json", "--json-schema", json.dumps(schema),
             "--strict-mcp-config", "--allowedTools", allowed, "--disallowedTools", disallowed],
            cwd=worktree, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_CLAUDE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return ({}, 0, "rate-limited")   # a stuck/rate-limited call -> defer + stop, never hang
    except OSError:
        return ({}, 0, "error")
    env = _parse_envelope(proc.stdout)
    tokens = _out_tokens(env)
    kind, _detail = classify_outcome(env, proc.stdout)
    if kind == "rate-limited":
        return ({}, tokens, "rate-limited")
    if kind in ("api-error", "no-envelope"):
        return ({}, tokens, "error")
    structured_output = env.get("structured_output") or {}
    if not structured_output:
        return ({}, tokens, "error")
    return (structured_output, tokens, "ok")


def run_plan(finding, worktree: Path) -> tuple[dict, int, str]:
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (PLAN_PROMPT.read_text(encoding="utf-8")
            .replace("{DIMENSION}", finding.dimension).replace("{FILE}", finding.file)
            .replace("{SUMMARY}", finding.summary))
    (prompt_dir / "plan.md").write_text(text, encoding="utf-8")
    so, tokens, status = _run_claude(worktree, "plan.md", PLAN_SCHEMA, "Read,Grep,Glob", "Edit,Write,Bash")
    return (so, tokens, status)


def run_impl(finding, plan: dict, worktree: Path, feedback: str = "") -> tuple[str, str, int]:
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    text = (IMPL_PROMPT.read_text(encoding="utf-8")
            .replace("{DIMENSION}", finding.dimension).replace("{FILE}", finding.file)
            .replace("{SUMMARY}", finding.summary)
            .replace("{ROOT_CAUSE}", str(plan.get("root_cause", "")))
            .replace("{APPROACH}", str(plan.get("approach", "")))
            .replace("{JUSTIFICATION}", str(plan.get("justification", "")))
            .replace("{FEEDBACK}", feedback or "(none)"))
    (prompt_dir / "impl.md").write_text(text, encoding="utf-8")
    so, tokens, status = _run_claude(worktree, "impl.md", IMPL_SCHEMA, "Read,Grep,Glob,Edit,Write", "Bash")
    if status != "ok":
        return (status, "", tokens)
    return (("applied" if so.get("applied") else "no-op"), str(so.get("self_critique") or ""), tokens)


def _plan_skeptic(finding, plan: dict, worktree: Path) -> tuple[str, str, int]:
    """Read-only adversarial check of the applied fix AGAINST its stated plan. Any failure ->
    ('confirmed', why, tokens) (never wrongly reject a real fix)."""
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt = (f"A fix was applied for: dimension={finding.dimension}, file={finding.file}, "
              f"claim={finding.summary}. The author's plan was: approach={plan.get('approach')}, "
              f"justification={plan.get('justification')}. Read the CURRENT code (with the fix) and the "
              f"plan. Decide whether the applied diff genuinely realizes the plan AND resolves the "
              f"finding WITHOUT changing behavior or introducing a new problem. Return verdict 'refuted' "
              f"ONLY if it does not; otherwise 'confirmed'.")
    (prompt_dir / "check.md").write_text(prompt, encoding="utf-8")
    so, tokens, status = _run_claude(worktree, "check.md", SKEPTIC_SCHEMA, "Read,Grep,Glob", "Edit,Write,Bash")
    if status != "ok":
        return ("confirmed", f"skeptic {status}", tokens)
    verdict = str(so.get("verdict") or "").strip().lower()
    reason = str(so.get("reason") or "").strip()
    return (("refuted" if verdict == "refuted" else "confirmed"), reason, tokens)


def run_rich_refactor(cfg, worktree, finding, *, run_verify, plan_agent=run_plan,
                      impl_agent=run_impl, skeptic=_plan_skeptic,
                      max_retries: int = 2) -> tuple[str, dict, int, str]:
    """Rich escalation for a refactor whose one-shot failed. Plan once, then implement + gate with up to
    max_retries targeted retries. Returns (outcome, plan, cost, reason). On 'fixed' the verified edit is
    left in the worktree (uncommitted) for the caller to commit+branch."""
    import gitops
    from gate import gate_fix

    cost = 0
    gitops.checkout_master(worktree)                 # clean, detached at master
    plan, tok, status = plan_agent(finding, worktree)
    cost += tok
    if status == "rate-limited":
        gitops.reset_hard_master(worktree)
        return ("rate-limited", plan, cost, "plan rate-limited")
    if status != "ok":
        gitops.reset_hard_master(worktree)
        return ("needs-human", plan, cost, "no usable plan produced")

    feedback = ""
    for _attempt in range(max_retries + 1):
        status, _critique, tok = impl_agent(finding, plan, worktree, feedback)
        cost += tok
        if status == "rate-limited":
            gitops.reset_hard_master(worktree)
            return ("rate-limited", plan, cost, "implement rate-limited")
        if status != "applied" or gitops.suite_is_clean(worktree):
            gitops.reset_hard_master(worktree)
            feedback = "your previous attempt made no change; implement the fix as planned"
            continue
        changed = gitops.changed_files(worktree)
        ok, reason, sk_tok = gate_fix(cfg, worktree, finding, changed, run_verify=run_verify,
                                      skeptic=lambda f, w: skeptic(f, plan, w))
        cost += sk_tok
        if ok:
            return ("fixed", plan, cost, "gate passed")     # leave the edit for the caller to commit
        if _attempt == max_retries:
            # last attempt failed the gate — preserve the actual attempt on a wip branch for the human
            # (the dossier links it) before cleaning the worktree.
            gitops.commit_and_branch(worktree, f"wip(needs-human): {finding.fingerprint[:50]}",
                                     gitops.wip_branch(finding.fingerprint))
            gitops.reset_hard_master(worktree)
            return ("needs-human", plan, cost, f"exhausted {max_retries} retries: {reason}")
        gitops.reset_hard_master(worktree)
        feedback = f"the gate rejected your fix: {reason}. Address exactly that and re-implement."
    return ("needs-human", plan, cost, f"exhausted {max_retries} retries: {feedback}")
