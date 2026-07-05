from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from claude_iterate import _claude_exe, _parse_envelope, classify_outcome  # reused helpers

FIX_PROMPT_PATH = Path(__file__).resolve().parent / "fix_prompt.md"

# Per-call hard cap on a nested `claude -p` turn (see rich._CLAUDE_TIMEOUT_S). No timeout = a
# rate-limited/stuck call hangs the whole loop for hours. On timeout -> rate-limited (defer + stop).
_CLAUDE_TIMEOUT_S = 600

FIX_SCHEMA: dict = {
    "type": "object",
    "properties": {"applied": {"type": "boolean"}, "summary": {"type": "string"}},
    "required": ["applied", "summary"],
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


def _build_fix_prompt(finding) -> str:
    return (FIX_PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{DIMENSION}", finding.dimension)
            .replace("{FILE}", finding.file)
            .replace("{SUMMARY}", finding.summary))


def run_fixer(finding, worktree: Path) -> tuple[str, int]:
    """Run the mutating fix agent (edits the worktree). Returns (outcome, output_tokens); outcome in
    {applied, no-op, rate-limited, error}. The agent may Edit/Write (NOT Bash) — the review-loop stays
    read-only; only the fix-loop mutates, and only within one finding."""
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "fix.md").write_text(_build_fix_prompt(finding), encoding="utf-8")
    short = ("Read the file .fl/fix.md relative to the current working directory and follow its "
             "instructions exactly, then return the object.")
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short,
             "--output-format", "json", "--json-schema", json.dumps(FIX_SCHEMA),
             "--strict-mcp-config",
             "--allowedTools", "Read,Grep,Glob,Edit,Write", "--disallowedTools", "Bash"],
            cwd=worktree, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_CLAUDE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return ("rate-limited", 0)   # stuck/rate-limited -> defer + stop, never hang
    except OSError as e:
        return ("error", 0)
    env = _parse_envelope(proc.stdout)
    tokens = _out_tokens(env)
    kind, _detail = classify_outcome(env, proc.stdout)
    if kind == "rate-limited":
        return ("rate-limited", tokens)
    if kind in ("api-error", "no-envelope"):
        return ("error", tokens)
    so = env.get("structured_output") or {}
    return (("applied" if so.get("applied") else "no-op"), tokens)


def skeptic_check(finding, worktree: Path) -> tuple[str, str, int]:
    """Adversarial self-check: does the just-applied fix address the finding without breaking something?
    Read-only. Any failure -> ('confirmed', why, tokens) (never wrongly reject a real fix)."""
    prompt = (f"A fix was just applied for this issue: dimension={finding.dimension}, "
              f"file={finding.file}, claim={finding.summary}. Read the CURRENT code (it now includes "
              f"the fix). Decide whether the fix genuinely addresses the issue without introducing a "
              f"new problem or changing behavior. Return verdict 'refuted' ONLY if the fix is wrong / "
              f"incomplete / behavior-changing; otherwise 'confirmed'.")
    prompt_dir = worktree / ".fl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "check.md").write_text(prompt, encoding="utf-8")
    short = ("Read the file .fl/check.md relative to the current working directory and follow it, "
             "then return the verdict object.")
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short,
             "--output-format", "json", "--json-schema", json.dumps(SKEPTIC_SCHEMA),
             "--strict-mcp-config", "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Edit,Write,Bash"],
            cwd=worktree, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_CLAUDE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return ("confirmed", "skeptic timed out", 0)   # fail-open (like OSError); next call stops the loop
    except OSError as e:
        return ("confirmed", f"skeptic could not run: {e}", 0)
    env = _parse_envelope(proc.stdout)
    tokens = _out_tokens(env)
    kind, detail = classify_outcome(env, proc.stdout)
    if kind in ("rate-limited", "api-error", "no-envelope"):
        return ("confirmed", f"skeptic {kind}: {detail}", tokens)
    so = env.get("structured_output") or {}
    verdict = str(so.get("verdict") or "").strip().lower()
    reason = str(so.get("reason") or "").strip()
    return (("refuted" if verdict == "refuted" else "confirmed"), reason or verdict, tokens)
