from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from adversarial import verify_findings
from analysis import run_analysis
from config import ReviewLoopConfig, load_config
from logsweep import run_log_sweep
from registry import write_registry
from report import Finding, IterationResult, render_report
from vaulttodo import run_vault_todo_sweep
from stops import StopController
from worktree import create_worktree, remove_worktree

IterateFn = Callable[[ReviewLoopConfig, Path, int], IterationResult]


def _log(msg):
    print(f"[review-loop] {msg}", flush=True)


def _branch(now: str) -> str:
    # Neutral prefix on purpose — a "review-loop" branch name makes the nested agent confabulate a
    # harness narrative and stop producing structured output. See loops/review-loop.
    return "rl/" + now.replace(" ", "-").replace(":", "")


# A static-analysis line starts with "<abs-path>.<ext>:<row> <rest>" (ruff/pyright/eslint/tsc). Extract
# the leading file path so the fix-loop knows WHICH file to open. Non-greedy up to the first ".<ext>:<n>"
# so a Windows drive "C:" (no digits after the colon) is not mistaken for the file:line separator.
_STATIC_HEAD = re.compile(r"^(?P<file>.+?\.\w+):\d+\b")


def _rel_static_file(line: str, repo_root: Path) -> str:
    """Repo-relative path of a static-analysis finding, or '' if unparseable. The analysis runs in
    repo_root, so the emitted path is absolute under it; strip that prefix case-insensitively (ruff emits
    'C:\\', pyright 'c:\\' on Windows) and normalise to forward slashes."""
    m = _STATIC_HEAD.match(line)
    if not m:
        return ""
    p = m.group("file").replace("\\", "/")
    root = str(repo_root).replace("\\", "/").rstrip("/")
    if p.lower().startswith(root.lower() + "/"):
        return p[len(root) + 1:]
    return p   # outside repo_root (or already relative) -> keep as-is, still better than empty


def run(repo_root: Path, iterate: IterateFn, now: str,
        max_iter_override: int | None = None) -> Path:
    cfg = load_config(repo_root)
    max_iter = max_iter_override if max_iter_override is not None else cfg.max_iter
    if max_iter < 1:
        raise ValueError(f"max_iter must be >= 1, got {max_iter}")
    branch = _branch(now)
    worktree = create_worktree(repo_root, branch)
    analysis_findings: list[str] = []
    analysis_errors: list[str] = []
    log_findings: list[str] = []
    log_errors: list[str] = []
    todo_findings: list[str] = []
    todo_errors: list[str] = []
    report_only_override: list | None = None
    refuted_findings: list = []
    skeptic_tokens = 0
    results: list[IterationResult] = []
    stop_reason = "max_iter"
    try:
        if cfg.analysis:
            # read-only tools; run where deps are installed (repo_root), not the deps-less worktree
            analysis_findings, analysis_errors = run_analysis(cfg, repo_root)
        if cfg.logfire:
            log_findings, log_errors = run_log_sweep(cfg)
        todo_findings, todo_errors = run_vault_todo_sweep(cfg, repo_root)
        sc = StopController(max_iter=max_iter, budget_tokens=cfg.budget_tokens)
        tokens = 0
        for i in range(1, max_iter + 1):
            res = iterate(cfg, worktree, i)
            results.append(res)
            tokens += res.tokens
            if not res.parsed:
                # Not a clean pass. Surface the real failure kind (rate-limited / api-error /
                # no-envelope / no-output) so the report never reads as "nothing found".
                stop_reason = res.failure_kind or "no-output"
                break
            cont, reason = sc.check(i, tokens, res.fingerprints)
            if not cont:
                stop_reason = reason
                break
        if any(r.parsed for r in results):
            report_only_all = [f for r in results for f in r.findings]
            if report_only_all:
                report_only_override, refuted_findings, skeptic_tokens = verify_findings(
                    worktree, report_only_all)
                _log(f"adversarial: {len(report_only_all)} findings -> "
                     f"{len(report_only_override)} survived")
    finally:
        remove_worktree(repo_root, worktree)

    # A "successful" stop that nonetheless had a per-layer pass fail (e.g. one layer rate-limited while
    # another produced findings) is only partially complete — don't let the frontmatter read as a
    # clean/full run. The report body already carries the per-layer failure banners.
    if stop_reason in ("clean", "max_iter", "stagnation", "budget") and any(
            r.layer_failures for r in results):
        stop_reason += "-partial"

    # Collect findings (LLM + static analysis) and write to the registry. Use the adversarial
    # SURVIVORS (report_only_override) when verify ran — refuted false-positives must NOT enter the
    # backlog the fix-loop consumes; only fall back to raw findings when no verify ran.
    reg_findings = (list(report_only_override) if report_only_override is not None
                    else [f for r in results for f in r.findings])
    # Wrap static-analysis findings as Finding objects (from string lines).
    for line in analysis_findings:
        reg_findings.append(Finding(
            fingerprint=f"static:{line[:80]}",
            file=_rel_static_file(line, repo_root),   # so the fix-loop can locate the file to edit
            line=None,
            dimension="static-analysis",
            severity="",
            layer="static",
            summary=line
        ))
    # Write registry atomically; never raises. The registry is the machine QUEUE for THIS repo — it lives
    # at the target repo root (gitignored), the single file all three loops share (review writes, fix
    # reads/mutates, integrate reads). Its parent being the repo also lets write_registry run
    # `git branch --merged` to tell merged fixes from regressions. Written BEFORE the report so its
    # reconciled rows can be rendered into the report's Bucket section.
    today = now.split(" ")[0]
    registry_path = repo_root / "bug-registry.md"
    # Absence (a registry row not re-detected) is only a trustworthy "resolved" signal when the scan
    # actually completed — a rate-limited/api-error/no-output/other run (or a -partial one) must not
    # settle rows just because it produced no findings.
    scan_complete = stop_reason in {"clean", "max_iter", "stagnation", "budget"}
    registry_rows = write_registry(registry_path, reg_findings, today, scan_complete=scan_complete)
    _log(f"registry: {len(reg_findings)} rows written")

    report_dir = (repo_root / cfg.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = now.replace(" ", "-").replace(":", "")
    report_path = report_dir / f"{stem}.md"
    report_path.write_text(
        render_report(repo_root.name, branch, results, stop_reason, now,
                      analysis_findings=analysis_findings, analysis_errors=analysis_errors,
                      log_findings=log_findings, log_errors=log_errors,
                      todo_findings=todo_findings, todo_errors=todo_errors,
                      report_only_override=report_only_override, refuted_findings=refuted_findings,
                      skeptic_tokens=skeptic_tokens, registry_rows=registry_rows),
        encoding="utf-8")
    # Persist raw agent output next to the report for observability/debugging.
    raw = "\n\n".join(r.raw for r in results if r.raw)
    if raw:
        (report_dir / f"{stem}.agent.log").write_text(raw, encoding="utf-8")

    return report_path
