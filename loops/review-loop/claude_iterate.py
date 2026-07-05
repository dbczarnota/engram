from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import ReviewLoopConfig
from gating import enabled_layers
from report import Finding, IterationResult

PROMPT_PATH = Path(__file__).resolve().parent / "iteration_prompt.md"

# Per-call hard cap on a nested `claude -p` review pass. Without it, a rate-limited/stuck call blocks
# subprocess.run indefinitely and hangs the whole fan-out. On timeout the pass yields nothing and the
# others proceed — never a multi-hour freeze.
_CLAUDE_TIMEOUT_S = 600

# Schema the agent's final answer is constrained to (claude -p --json-schema). The result lands
# in the envelope's `structured_output` field — no prose parsing, no file handoff.
FINDINGS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                # Keep this schema simple: a JSON-Schema union type (e.g. {"type":["string","null"]})
                # makes claude -p --json-schema silently fall back to prose (no structured_output).
                "properties": {
                    "fingerprint": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "severity": {"type": "string"},
                    "summary": {"type": "string"},
                    "dimension": {"type": "string"},
                },
                "required": ["fingerprint", "file", "summary", "dimension"],
            },
        },
    },
    "required": ["findings"],
}


def _log(msg):
    print(f"[review-loop] {msg}", flush=True)


class ClaudeNotFound(RuntimeError):
    """The `claude` CLI could not be resolved on PATH."""


def _claude_exe() -> str:
    # On Windows `claude` is a `.CMD` shim, not a real `.exe`; subprocess with a bare
    # name fails with WinError 2 because CreateProcess ignores PATHEXT. shutil.which
    # honours PATHEXT and returns the full path (e.g. ...\claude.CMD), which Python 3.12
    # subprocess executes directly with shell=False. See lessons/windows-dev.md.
    exe = shutil.which("claude")
    if not exe:
        raise ClaudeNotFound("`claude` CLI not found on PATH")
    return exe


_PROMPT_DIMENSIONS = [
    ("bug-hunt", "real correctness bugs: null/None deref, wrong conditionals, off-by-one, unhandled "
                 "error paths, races, resource leaks, exception swallowing, type-coercion, wrong API "
                 "usage, data-loss"),
    ("security", "injection, XSS, authz/authn gaps, unsafe deserialization, secret leakage, SSRF, "
                 "path traversal"),
    ("dead-code", "unreachable or unused code, legacy paths no longer called, dead branches, orphaned "
                  "exports"),
    ("dedup", "duplicated logic that should be extracted and reused"),
    ("complexity", "needless complexity that could be simplified WITHOUT changing behavior"),
    ("perf", "concrete performance problems (N+1 queries, quadratic loops, repeated work) — not "
             "micro-optimizations"),
    ("consistency", "violations of this repo's own conventions/standards (e.g. its CLAUDE.md)"),
]


def _dimension_block(dims=None) -> str:
    dims = _PROMPT_DIMENSIONS if dims is None else dims
    return "\n".join(f"- **{name}** — {scope}" for name, scope in dims)


def _parse_envelope(stdout: str) -> dict:
    """Parse the `claude -p --output-format json` result envelope. Returns {} if stdout
    is not that envelope (e.g. claude printed prose instead of the JSON result)."""
    try:
        env = json.loads(stdout)
        return env if isinstance(env, dict) else {}
    except json.JSONDecodeError:
        return {}


_SESSION_CAP_MARKERS = ("session limit", "usage limit", "resets")


def classify_outcome(env: dict, stdout: str) -> tuple[str, str]:
    """Split the claude-result envelope into one outcome + a human-readable detail."""
    if not env:
        text = (stdout or "").strip()
        # A session/usage cap can surface as prose (not a JSON error envelope). Treat it as
        # rate-limited so it isn't futilely retried like a transient no-envelope blip.
        if any(m in text.lower() for m in _SESSION_CAP_MARKERS):
            return ("rate-limited", text[:200] or "rate limited")
        return ("no-envelope", text[:200] or "no JSON result envelope")
    if env.get("is_error"):
        status = env.get("api_error_status")
        msg = str(env.get("result") or "").strip()
        if status == 429 or any(m in msg.lower() for m in _SESSION_CAP_MARKERS):
            return ("rate-limited", msg or "rate limited (HTTP 429)")
        return ("api-error", f"HTTP {status}: {msg}" if status else (msg or "unknown API error"))
    so = env.get("structured_output")
    findings = so.get("findings") if isinstance(so, dict) else None
    if not isinstance(findings, list):
        return ("no-output", "schema fallback — no structured_output")
    return ("ok", "")


def parse_result(env: dict, stdout: str = "", layer: str = "all") -> IterationResult:
    """Build an IterationResult from a claude result envelope for one layer's pass. Non-`ok`
    outcomes -> parsed=False with failure_kind/error_detail. `ok` -> findings tagged with layer."""
    kind, detail = classify_outcome(env, stdout)
    if kind != "ok":
        return IterationResult(parsed=False, failure_kind=kind, error_detail=detail)
    so = env.get("structured_output") or {}
    raw_findings = so.get("findings") or []
    fingerprints: set[str] = set()
    findings: list[Finding] = []
    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        summary = str(f.get("summary") or "")
        fp = str(f.get("fingerprint") or summary or "unknown")
        fingerprints.add(fp)
        line = f.get("line")
        findings.append(Finding(
            fingerprint=fp, file=str(f.get("file") or ""),
            line=int(line) if isinstance(line, int) else None,
            dimension=str(f.get("dimension") or "bug-hunt"),
            severity=str(f.get("severity") or ""), layer=layer, summary=summary or fp))
    tokens = 0
    try:
        tokens = int((env.get("usage") or {}).get("output_tokens") or 0)
    except (AttributeError, TypeError, ValueError):
        tokens = 0
    return IterationResult(fingerprints=fingerprints, findings=findings,
                           tokens=tokens, parsed=True, layers_reviewed=[layer])


def _build_prompt(cfg: ReviewLoopConfig, layer: str, paths: list[str], dims=None) -> str:
    return (PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{LAYER}", layer)
            .replace("{PATHS}", ", ".join(paths) or "(whole repo)")
            .replace("{DIMENSIONS}", _dimension_block(dims)))


def _allowed_tools(cfg: ReviewLoopConfig) -> str:
    # Report-only reviews: read-only access (never apply fixes).
    return "Read,Grep,Glob"


def _passes(cfg: ReviewLoopConfig) -> list[tuple[str, list[str], list]]:
    """The (layer, paths, dims) passes for one iteration. Monolith: one pass per layer covering all
    dimensions. Fan-out: one focused pass per (layer, dimension)."""
    tasks: list[tuple[str, list[str], list]] = []
    for layer, paths in enabled_layers(cfg):
        if cfg.fanout:
            for name, scope in _PROMPT_DIMENSIONS:
                tasks.append((layer, paths, [(name, scope)]))
        else:
            tasks.append((layer, paths, list(_PROMPT_DIMENSIONS)))
    return tasks


_TRANSIENT_KINDS = {"api-error", "no-envelope"}


def _is_retryable(res: IterationResult) -> bool:
    """Transient failures are worth another attempt; a subscription session/usage cap and a
    deterministic no-output are not."""
    kind = res.failure_kind
    if kind in _TRANSIENT_KINDS:
        return True
    if kind == "rate-limited":
        detail = (res.error_detail or "").lower()
        return not any(m in detail for m in _SESSION_CAP_MARKERS)
    return False


def _retry(run_once, *, max_attempts: int, base_delay: float, sleep) -> IterationResult:
    logs: list[str] = []
    result: IterationResult | None = None
    for attempt in range(1, max_attempts + 1):
        result, log = run_once(attempt)
        logs.append(log)
        if result.parsed or not _is_retryable(result) or attempt == max_attempts:
            break
        sleep(base_delay * (2 ** (attempt - 1)))
    assert result is not None
    result.raw = "\n\n".join(logs)
    return result


def _iterate_layer(cfg: ReviewLoopConfig, worktree: Path, iteration: int, layer: str,
                   paths: list[str], dims, *, max_attempts: int, base_delay: float, sleep) -> IterationResult:
    prompt_dir = worktree / ".rl"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    # Unique per pass: fan-out passes run concurrently, so a shared prompt filename would race.
    name = f"prompt-{uuid.uuid4().hex}.md"
    (prompt_dir / name).write_text(_build_prompt(cfg, layer, paths, dims), encoding="utf-8")
    short = (f"Read the file .rl/{name} relative to the current working directory and follow its "
             "instructions exactly, then return the findings object.")

    def run_once(attempt: int) -> tuple[IterationResult, str]:
        try:
            proc = subprocess.run(
                # Chinese Wall: NO --permission-mode acceptEdits (it auto-approves Edit/Write in headless
                # regardless of --allowedTools). Read-only tools + an explicit disallow = hard boundary,
                # matching the skeptic pass. The review-loop must never mutate target-repo code.
                [_claude_exe(), "-p", short,
                 "--output-format", "json", "--json-schema", json.dumps(FINDINGS_SCHEMA),
                 "--strict-mcp-config",
                 "--allowedTools", _allowed_tools(cfg), "--disallowedTools", "Edit,Write,Bash"],
                cwd=worktree, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "REVIEWLOOP_NESTED": "1"}, timeout=_CLAUDE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            # A stuck/rate-limited pass must not hang the fan-out. Yield an empty (failed) pass and let
            # the other passes proceed — never block for hours on one call.
            res = parse_result({}, "", layer)
            return (res, f"$ claude -p (iteration {iteration}, layer {layer}) TIMED OUT after {_CLAUDE_TIMEOUT_S}s")
        env = _parse_envelope(proc.stdout)
        res = parse_result(env, proc.stdout, layer)
        log = (f"$ claude -p (iteration {iteration}, layer {layer}, dims {[d[0] for d in dims]}, "
               f"attempt {attempt})  is_error={env.get('is_error')} kind={res.failure_kind} "
               f"num_turns={env.get('num_turns')}\n--STDOUT--\n{proc.stdout}\n--STDERR--\n{proc.stderr}")
        return (res, log)

    return _retry(run_once, max_attempts=max_attempts, base_delay=base_delay, sleep=sleep)


def _merge_layers(pairs: list[tuple[str, IterationResult]]) -> IterationResult:
    merged = IterationResult()
    for layer, sub in pairs:
        merged.fingerprints |= sub.fingerprints
        merged.findings += sub.findings
        merged.tokens += sub.tokens
        if sub.parsed:
            merged.layers_reviewed.append(layer)
        else:
            merged.layer_failures.append((layer, f"{sub.failure_kind}: {sub.error_detail}".strip(": ")))
    merged.raw = "\n\n".join(sub.raw for _, sub in pairs if sub.raw)
    merged.parsed = any(sub.parsed for _, sub in pairs)
    if not merged.parsed and pairs:
        first = pairs[0][1]
        merged.failure_kind = first.failure_kind
        merged.error_detail = first.error_detail
    return merged


def claude_iterate(cfg: ReviewLoopConfig, worktree: Path, iteration: int, *,
                   max_attempts: int = 3, base_delay: float = 2.0, sleep=time.sleep,
                   max_workers: int = 4, _layer_runner=_iterate_layer) -> IterationResult:
    tasks = _passes(cfg)

    def _run(task):
        layer, paths, dims = task
        sub = _layer_runner(cfg, worktree, iteration, layer, paths, dims,
                            max_attempts=max_attempts, base_delay=base_delay, sleep=sleep)
        label = f"{layer}/{','.join(d[0] for d in dims)}"
        _log(f"  pass done: {label} ({len(sub.findings)} findings)")
        return (layer, sub)

    _log(f"iteration {iteration}: {len(tasks)} pass(es) [{'fanout' if cfg.fanout else 'monolith'}]")
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(tasks)))) as ex:
        pairs = list(ex.map(_run, tasks))   # ex.map preserves task order
    return _merge_layers(pairs)
