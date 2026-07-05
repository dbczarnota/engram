from __future__ import annotations

import json
import os
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from claude_iterate import ClaudeNotFound, _claude_exe, _parse_envelope, classify_outcome

SKEPTIC_PROMPT_PATH = Path(__file__).resolve().parent / "skeptic_prompt.md"

SKEPTIC_SCHEMA: dict = {
    "type": "object",
    "properties": {"verdict": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["verdict", "reason"],
}


def _build_skeptic_prompt(finding) -> str:
    return (SKEPTIC_PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{DIMENSION}", finding.dimension)
            .replace("{SUMMARY}", finding.summary))


def _run_skeptic(finding, worktree: Path) -> tuple[str, str, int]:
    """Run one read-only skeptic pass. Returns (verdict, reason, output_tokens). Any failure ->
    ("confirmed", why, tokens): a broken skeptic must never drop a real finding."""
    prompt_dir = worktree / ".rl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    # Unique per call: skeptics run concurrently, so a shared prompt filename would race (one skeptic
    # overwriting another's prompt before claude reads it → verifying the wrong claim).
    name = f"skeptic-{uuid.uuid4().hex}.md"
    (prompt_dir / name).write_text(_build_skeptic_prompt(finding), encoding="utf-8")
    short = (f"Read the file .rl/{name} relative to the current working directory and follow its "
             "instructions exactly, then return the verdict object.")
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short,
             "--output-format", "json", "--json-schema", json.dumps(SKEPTIC_SCHEMA),
             "--strict-mcp-config", "--allowedTools", "Read,Grep,Glob"],
            cwd=worktree, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"})
    except (OSError, ClaudeNotFound) as e:
        return ("confirmed", f"skeptic could not run: {e}", 0)
    env = _parse_envelope(proc.stdout)
    tokens = 0
    try:
        tokens = int((env.get("usage") or {}).get("output_tokens") or 0)
    except (AttributeError, TypeError, ValueError):
        tokens = 0
    kind, detail = classify_outcome(env, proc.stdout)
    # NOTE: classify_outcome's "ok" is findings-list-specific (the review schema). The skeptic schema
    # is {verdict, reason}, so a *successful* skeptic run classifies as "no-output" — treat only the
    # genuine failure kinds as errors; otherwise read the verdict directly.
    if kind in ("rate-limited", "api-error", "no-envelope"):
        return ("confirmed", f"skeptic {kind}: {detail}", tokens)
    so = env.get("structured_output") or {}
    verdict = str(so.get("verdict") or "").strip().lower()
    reason = str(so.get("reason") or "").strip()
    if verdict == "refuted":
        return ("refuted", reason or "refuted by skeptic", tokens)
    return ("confirmed", reason or "confirmed by skeptic", tokens)


def verify_findings(worktree: Path, findings: list, *, review=_run_skeptic,
                    max_checks: int = 20, max_workers: int = 4) -> tuple[list, list, int]:
    """Adversarially check each report-only finding. Returns (survivors, refuted, skeptic_tokens).
    survivors are `Finding`s; refuted are `(Finding, reason)` pairs.
    Findings beyond max_checks survive unverified (cost cap). Only verdict=="refuted" filters a finding.

    The skeptic passes run concurrently (bounded by max_workers) — they are independent, read-only,
    and I/O-bound. A review that raises is treated as confirmed (survivor) — a broken skeptic must
    never drop a real finding. Original order is preserved in the output. `review` may return
    (verdict, reason) or (verdict, reason, tokens); a missing token count is treated as 0."""
    to_check = findings[:max_checks]
    extra = findings[max_checks:]

    def _one(finding):
        try:
            return review(finding, worktree)
        except Exception as e:  # a raising skeptic must not drop the finding
            return ("confirmed", f"skeptic error: {e}", 0)

    results: list = []
    if to_check:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(to_check))) as ex:
            results = list(ex.map(_one, to_check))  # ex.map preserves input order

    survivors: list = []
    refuted: list = []
    skeptic_tokens = 0
    for finding, res in zip(to_check, results):
        verdict, reason = res[0], res[1]
        skeptic_tokens += res[2] if len(res) > 2 else 0
        if verdict == "refuted":
            refuted.append((finding, reason))
        else:
            survivors.append(finding)
    survivors.extend(extra)  # beyond the cap: unverified survivors, order preserved
    return (survivors, refuted, skeptic_tokens)
