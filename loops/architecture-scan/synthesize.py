from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from models import Candidate, DesignProposal, RFC

SYN_PROMPT_PATH = Path(__file__).resolve().parent / "synthesize_prompt.md"
_TIMEOUT_S = 600

SYN_SCHEMA: dict = {
    "type": "object",
    "properties": {"recommendation": {"type": "string"}, "rfc_markdown": {"type": "string"}},
    "required": ["recommendation", "rfc_markdown"],
}


def _build_prompt(candidate: Candidate, proposals: list[DesignProposal]) -> str:
    payload = json.dumps([asdict(p) for p in proposals], ensure_ascii=False)
    return (SYN_PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{QUALIFIED_NAME}", candidate.qualified_name)
            .replace("{FILE}", candidate.file)
            .replace("{PROPOSALS_JSON}", payload))


def _spawn_agent(candidate: Candidate, proposals: list[DesignProposal], repo_root: Path) -> tuple[str, str]:
    # Lazy import to keep module import clean for tests
    from claude_iterate import _claude_exe, _parse_envelope, classify_outcome

    prompt_dir = Path(repo_root) / ".as"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / "synthesize.md").write_text(_build_prompt(candidate, proposals), encoding="utf-8")
    short = ("Read the file .as/synthesize.md relative to the current working directory and follow it, "
             "then return the object.")
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short, "--output-format", "json",
             "--json-schema", json.dumps(SYN_SCHEMA), "--strict-mcp-config",
             "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Edit,Write,Bash"],
            cwd=repo_root, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return ("", "")
    env = _parse_envelope(proc.stdout)
    kind, _ = classify_outcome(env, proc.stdout)
    if kind in ("rate-limited", "api-error", "no-envelope"):
        return ("", "")
    so = env.get("structured_output") or {}
    return (str(so.get("recommendation", "")), str(so.get("rfc_markdown", "")))


def synthesize_rfc(candidate: Candidate, proposals: list[DesignProposal], repo_root: Path,
                   *, agent_fn=None) -> RFC:
    agent_fn = agent_fn or _spawn_agent
    recommendation, markdown = agent_fn(candidate, proposals, repo_root)
    return RFC(candidate=candidate, recommendation=recommendation, markdown=markdown)
