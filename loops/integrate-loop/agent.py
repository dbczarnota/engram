from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from claude_iterate import _claude_exe, _parse_envelope, classify_outcome

_DIR = Path(__file__).resolve().parent
PROMPT = _DIR / "agent_prompt.md"
_TIMEOUT_S = 600
_SCHEMA = {"type": "object",
           "properties": {"tier": {"type": "string"}, "rationale": {"type": "string"}},
           "required": ["tier", "rationale"]}
_TIERS = {"prod-safe", "canary", "needs-human"}


def assess(finding_summary, dimension, floor, signals, branch, repo, *, diff_text: str = "") -> tuple[str, str, int]:
    prompt_dir = repo / ".il"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    text = (PROMPT.read_text(encoding="utf-8")
            .replace("{BRANCH}", branch).replace("{SUMMARY}", finding_summary or "")
            .replace("{DIMENSION}", dimension or "").replace("{FLOOR}", floor)
            .replace("{SIGNALS}", str(signals)).replace("{DIFF}", diff_text or ""))
    (prompt_dir / "assess.md").write_text(text, encoding="utf-8")
    short = "Read the file .il/assess.md relative to the cwd and follow it exactly, then return the object."
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short, "--output-format", "json", "--json-schema", json.dumps(_SCHEMA),
             "--strict-mcp-config", "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Edit,Write,Bash"],
            cwd=repo, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return (floor, "agent unavailable — floor kept", 0)
    env = _parse_envelope(proc.stdout)
    tokens = int((env.get("usage") or {}).get("output_tokens") or 0)
    kind, _detail = classify_outcome(env, proc.stdout)
    so = env.get("structured_output") or {}
    if kind in ("rate-limited", "api-error", "no-envelope") or not so:
        return (floor, "agent unavailable — floor kept", tokens)
    tier = str(so.get("tier") or "").strip().lower()
    if tier not in _TIERS:
        return (floor, "agent returned an unknown tier — floor kept", tokens)
    return (tier, str(so.get("rationale") or "").strip(), tokens)
