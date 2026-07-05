from __future__ import annotations

from dataclasses import dataclass, field

_LLM_DIMENSIONS_LINE = ("Dimensions reviewed (LLM): bug-hunt, security, dead-code, dedup, complexity, "
                        "perf, consistency. log-sweep: deferred (needs Logfire MCP).")


@dataclass
class Finding:
    fingerprint: str
    file: str
    line: int | None
    dimension: str
    severity: str
    layer: str
    summary: str


@dataclass
class IterationResult:
    fingerprints: set[str] = field(default_factory=set)
    findings: list[Finding] = field(default_factory=list)
    tokens: int = 0
    # False when the agent produced no parseable findings file — this is NOT a clean
    # pass, it means the iteration yielded no usable result and must not be reported as
    # "found nothing".
    parsed: bool = True
    # Raw agent stdout/stderr for the iteration, persisted next to the report for debugging.
    raw: str = ""
    # Populated when parsed is False: which failure occurred and a human-readable detail.
    # kinds: "rate-limited" | "api-error" | "no-envelope" | "no-output" (None when parsed).
    failure_kind: str | None = None
    error_detail: str = ""
    # Per-layer pass failures within one iteration: (layer, "<kind>: <detail>"). A layer can fail
    # (e.g. rate-limited) while another layer still produced findings.
    layer_failures: list[tuple[str, str]] = field(default_factory=list)
    # Layers whose pass parsed OK this iteration (for the "Layers reviewed" report line).
    layers_reviewed: list[str] = field(default_factory=list)


def render_report(repo_name: str, branch: str, results: list[IterationResult],
                  stop_reason: str, started_at: str,
                  analysis_findings: list[str] | None = None,
                  analysis_errors: list[str] | None = None,
                  log_findings: list[str] | None = None,
                  log_errors: list[str] | None = None,
                  todo_findings: list[str] | None = None,
                  todo_errors: list[str] | None = None,
                  report_only_override: list | None = None,
                  refuted_findings: list | None = None,
                  skeptic_tokens: int = 0,
                  registry_rows: list[dict] | None = None) -> str:
    analysis_findings = analysis_findings or []
    analysis_errors = analysis_errors or []
    log_findings = log_findings or []
    log_errors = log_errors or []
    todo_findings = todo_findings or []
    todo_errors = todo_errors or []
    findings = (report_only_override if report_only_override is not None
               else [f for r in results for f in r.findings])
    refuted_findings = refuted_findings or []
    tokens = sum(r.tokens for r in results)
    fm = [
        "---",
        "type: loop-report",
        f"project: {repo_name}",
        f"date: {started_at}",
        "read: false",
        f"branch: {branch}",
        f"iterations: {len(results)}",
        f"findings: {len(findings)}",
        f"refuted: {len(refuted_findings)}",
        f"analysis_findings: {len(analysis_findings)}",
        f"log_findings: {len(log_findings)}",
        f"vault_todos: {len(todo_findings)}",
        f"tokens: {tokens}",
        f"skeptic_tokens: {skeptic_tokens}",
        f"stop_reason: {stop_reason}",
        "---",
        "",
    ]
    body = [f"# review-loop report — {repo_name}", "",
            f"Branch `{branch}` · stop: **{stop_reason}** · {len(results)} iteration(s) · {tokens} tokens."]
    if any(r.parsed for r in results):
        body += ["", _LLM_DIMENSIONS_LINE]
    layers_reviewed = sorted({l for r in results for l in r.layers_reviewed})
    if layers_reviewed:
        body += ["", f"Layers reviewed: {', '.join(layers_reviewed)}."]
    for layer, why in [lf for r in results for lf in r.layer_failures]:
        body += ["", f"> ⚠️ **Layer `{layer}` did not complete: {why}.**"]
    detail = next((r.error_detail for r in results if r.failure_kind and r.error_detail), "")
    if stop_reason == "rate-limited":
        body += ["",
                 "> ⚠️ **The review was RATE-LIMITED (hit the session/usage limit) — it "
                 "never ran. This is NOT a clean pass.**"]
        if detail:
            body += [f"> {detail}"]
    elif stop_reason == "api-error":
        body += ["",
                 "> ⚠️ **The review hit an API error — this is NOT a clean pass.**"]
        if detail:
            body += [f"> {detail}"]
    elif stop_reason in ("no-output", "no-envelope"):
        body += ["",
                 "> ⚠️ **The agent produced no parseable findings file — this is NOT a "
                 "clean pass.**",
                 "> The review did not yield a usable result (see the `.agent.log` sidecar). "
                 "Do not read the empty sections below as \"reviewed, nothing found\"."]
        if detail:
            body += [f"> {detail}"]
    body += ["", "## Findings (report-only — you are the gate)"]
    if findings:
        by_layer: dict[str, dict[str, list[str]]] = {}
        for f in findings:
            by_layer.setdefault(f.layer, {}).setdefault(f.dimension, []).append(f.summary)
        for layer in sorted(by_layer):
            body += [f"### {layer}"]
            for dim in sorted(by_layer[layer]):
                body += [f"#### {dim}"] + [f"- {s}" for s in by_layer[layer][dim]]
    else:
        body += ["- (none)"]
    if refuted_findings:
        body += ["", "## Filtered out (refuted by adversarial check)"]
        for finding, reason in refuted_findings:
            body += [f"- [{finding.layer}/{finding.dimension}] {finding.summary}",
                     f"  ↳ refuted: {reason}"]
    if analysis_findings or analysis_errors:
        body += ["", "## Static analysis"]
        body += [f"- {x}" for x in analysis_findings] or ["- (no issues)"]
        if analysis_errors:
            body += ["", "> tool errors:"] + [f"> - {e}" for e in analysis_errors]
    if log_findings or log_errors:
        body += ["", "## Log errors (Logfire)"]
        body += [f"- {x}" for x in log_findings] or ["- (no recent errors)"]
        if log_errors:
            body += ["", "> sweep notes:"] + [f"> - {e}" for e in log_errors]
    if todo_findings or todo_errors:
        body += ["", "## Vault TODOs (open — surfaced, not fixed)"]
        body += [f"- {x}" for x in todo_findings] or ["- (none open)"]
        if todo_errors:
            body += ["", "> sweep notes:"] + [f"> - {e}" for e in todo_errors]
    bucket = _bucket_section(registry_rows or [])
    if bucket:
        body += ["", bucket.strip("\n")]
    body += ["", "> This branch was never merged or deployed. You are the gate."]
    return "\n".join(fm + body) + "\n"


_OPEN = ("pending", "needs-human", "regressed", "in-progress")


def _bucket_section(rows: list[dict]) -> str:
    if not rows:
        return ""
    from collections import Counter
    tally = Counter(r.get("status", "") for r in rows)
    counts = " · ".join(f"{k} {tally[k]}" for k in sorted(tally))
    lines = ["\n## Bucket\n", counts, ""]
    open_rows = [r for r in rows if r.get("status") in _OPEN]
    ready = [r for r in rows if r.get("status") == "fixed"]
    resolved = [r for r in rows if r.get("status") == "resolved"]
    lines.append(f"\n### OPEN ({len(open_rows)})")
    for r in open_rows:
        lines.append(f"- [{r.get('status')}] `{r.get('file','')}` — {r.get('summary','')[:120]}  ({r.get('fingerprint','')})")
    lines.append(f"\n### Ready to deploy — fixed ({len(ready)})")
    for r in ready:
        lines.append(f"- `{r.get('branch','')}` — {r.get('summary','')[:100]}")
    lines.append(f"\n### Resolved (total {len(resolved)})")
    for r in resolved:
        lines.append(f"- {r.get('fingerprint','')}")
    return "\n".join(lines) + "\n"
