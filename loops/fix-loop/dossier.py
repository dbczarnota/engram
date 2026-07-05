from __future__ import annotations

from pathlib import Path


def render_dossier(finding, reason: str, plan: dict | None, wip: str | None = None) -> str:
    """A needs-human hand-off note: the finding, why the loop deferred it, the loop's own root-cause
    analysis (its plan), and — when the loop's last attempt reached the gate — a `wip/…` branch holding
    the ACTUAL attempt (its diff, and for a bug its regression test). So a human (or a richer future loop)
    picks up with the loop's real code, not from zero."""
    lines = [
        f"# needs-human dossier — {finding.fingerprint}", "",
        f"**File:** {finding.file or '—'}  ·  **Dimension:** {finding.dimension or '—'}  ·  "
        f"**Severity:** {finding.severity or '—'}", "",
        "## Finding", finding.summary or "(no summary)", "",
        "## Why the loop deferred it", reason or "(no reason)", "",
    ]
    if plan:
        lines += [
            "## The loop's analysis (its plan before it gave up)",
            f"- **Root cause:** {plan.get('root_cause', '—')}",
            f"- **Chosen approach:** {plan.get('approach', '—')}",
            f"- **Alternatives considered:** {plan.get('alternatives', '—')}",
            f"- **Justification:** {plan.get('justification', '—')}", "",
        ]
    if wip:
        lines += [
            "## The loop's last attempt (preserved)",
            f"The loop's rejected attempt is on branch `{wip}` — `git checkout {wip}` to see its diff "
            "(and, for a bug, the regression test it wrote). The gate rejected it; start from there.", "",
        ]
    else:
        lines += ["> The attempt was not preserved (the loop gave up before a gate-reaching attempt).", ""]
    lines += ["> Start from the root-cause + approach above; the loop verified the gate rejected its attempt."]
    return "\n".join(lines) + "\n"


def write_dossier(dossier_dir: Path, finding, reason: str, plan: dict | None, wip: str | None = None) -> Path:
    dossier_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "-" for c in finding.fingerprint)[:60].strip("-") or "finding"
    path = dossier_dir / f"{slug}.md"
    path.write_text(render_dossier(finding, reason, plan, wip), encoding="utf-8")
    return path
