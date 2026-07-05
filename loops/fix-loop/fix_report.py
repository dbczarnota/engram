from __future__ import annotations


def render_fix_report(repo_name: str, now: str, *, fixed: list, failed: list, deferred: list,
                      budget_spent: int, budget_total: int, stop_reason: str,
                      repaired: list = (), repair_needs_human: list = (),
                      blocked_env: list = (), subsumed: list = ()) -> str:
    fm = ["---", "type: fix-loop-report", f"project: {repo_name}", f"date: {now}", "read: false",
          f"fixed: {len(fixed)}", f"failed: {len(failed)}", f"deferred: {len(deferred)}",
          f"budget_spent: {budget_spent}", f"budget_total: {budget_total}",
          f"stop_reason: {stop_reason}", "---", ""]
    body = [f"# fix-loop report — {repo_name}", "",
            f"Fixed {len(fixed)} · failed {len(failed)} · deferred {len(deferred)} · "
            f"spent {budget_spent}/{budget_total} tokens · stop: **{stop_reason}**."]
    if repaired or repair_needs_human or blocked_env:
        body += ["", "## Baseline repair"]
        body += [f"- repaired: {len(repaired)} · needs-human: {len(repair_needs_human)} · "
                f"blocked-environment: {len(blocked_env)}"]
        body += [f"- repaired `{r['id']}` -> `{r['branch']}` ({r.get('cost', '?')} tok)" for r in repaired]
        for r in repair_needs_human:
            if r.get("kind") == "proposed-test-change":
                body.append(f"- HIGH-SCRUTINY (review the test change) `{r['id']}` -> "
                            f"`{r.get('branch', '?')}`: {r['reason']}")
            else:
                body.append(f"- needs-human `{r['id']}`: {r['reason']}")
        body += [f"- blocked-environment: {b}" for b in blocked_env]
    body += ["", "## Fixed (branches ready — test → merge → canary)"]
    body += [f"- [{f.get('dimension')}] {f.get('summary')}  →  `{f.get('branch')}` ({f.get('cost')} tok)"
             for f in fixed] or ["- (none)"]
    body += ["", "## Failed / needs-human"]
    if failed:
        for f in failed:
            line = f"- [{f.get('dimension')}] {f.get('summary')}  ↳ {f.get('reason')}"
            if f.get("dossier"):
                line += f"  · dossier: `{f['dossier']}`"
            body.append(line)
    else:
        body.append("- (none)")
    body += ["", "## Deferred (rate-limited — next run)"]
    body += [f"- [{f.get('dimension')}] {f.get('summary')}" for f in deferred] or ["- (none)"]
    if subsumed:
        body += ["", "## Subsumed (covered by a sibling fix — no separate work)"]
        body += [f"- [{s.get('dimension')}] {s.get('summary')}  ↳ covered by `{s.get('subsumed_by')}`"
                 for s in subsumed]
    body += ["", "> The fix-loop never merges or deploys. You are the gate."]
    return "\n".join(fm + body) + "\n"
