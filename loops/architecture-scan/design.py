from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
from pathlib import Path

from models import Candidate, DesignProposal

DESIGN_PROMPT_PATH = Path(__file__).resolve().parent / "design_prompt.md"
_TIMEOUT_S = 600

PHILOSOPHIES: list[tuple[str, str]] = [
    ("phase-pipeline",
     "an explicit linear PHASE PIPELINE — model the unit as an ordered list of named phases, each a "
     "deep module with a narrow signature, threaded by one context object; the entry point becomes a "
     "~10-line driver that iterates phases."),
    ("strategy-outcome",
     "polymorphic STRATEGY objects + a uniform OUTCOME result type — each pathway implements a common "
     "attempt()->Outcome interface, and the duplicated ceremony collapses into ONE outcome handler."),
    ("functional-core",
     "FUNCTIONAL CORE / IMPERATIVE SHELL — extract a PURE decision engine (state, last_result) -> "
     "(new_state, next_effect); a thin shell interprets data-described effects against the real world."),
]

DESIGN_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "interface": {"type": "string"},
        "deep_modules": {"type": "string"},
        "weakness": {"type": "string"},
    },
    "required": ["interface", "deep_modules", "weakness"],
}


def _build_prompt(candidate: Candidate, philosophy: str) -> str:
    return (DESIGN_PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{QUALIFIED_NAME}", candidate.qualified_name)
            .replace("{FILE}", candidate.file)
            .replace("{LINES}", f"{candidate.line_start}-{candidate.line_end}")
            .replace("{PHILOSOPHY}", philosophy))


def _spawn_agent(candidate: Candidate, key: str, philosophy: str, repo_root: Path) -> DesignProposal:
    # Lazy import: only imported when actually spawning agents (not during test import)
    from claude_iterate import _claude_exe, _parse_envelope, classify_outcome

    prompt_dir = Path(repo_root) / ".as"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / f"design-{key}.md").write_text(_build_prompt(candidate, philosophy), encoding="utf-8")
    short = (f"Read the file .as/design-{key}.md relative to the current working directory and follow "
             f"it exactly, then return the object.")
    try:
        proc = subprocess.run(
            [_claude_exe(), "-p", short, "--output-format", "json",
             "--json-schema", json.dumps(DESIGN_SCHEMA), "--strict-mcp-config",
             "--allowedTools", "Read,Grep,Glob", "--disallowedTools", "Edit,Write,Bash"],
            cwd=repo_root, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return DesignProposal(philosophy=key, interface="", deep_modules="", weakness="", ok=False)
    env = _parse_envelope(proc.stdout)
    kind, _ = classify_outcome(env, proc.stdout)
    if kind in ("rate-limited", "api-error", "no-envelope"):
        return DesignProposal(philosophy=key, interface="", deep_modules="", weakness="", ok=False)
    so = env.get("structured_output") or {}
    return DesignProposal(philosophy=key, interface=str(so.get("interface", "")),
                          deep_modules=str(so.get("deep_modules", "")),
                          weakness=str(so.get("weakness", "")), ok=True)


def design_interfaces(candidate: Candidate, repo_root: Path, *, agent_fn=None,
                      max_workers: int = 3) -> list[DesignProposal]:
    agent_fn = agent_fn or _spawn_agent
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(agent_fn, candidate, key, phil, repo_root) for key, phil in PHILOSOPHIES]
        return [f.result() for f in futs]
