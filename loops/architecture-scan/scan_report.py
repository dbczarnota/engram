from __future__ import annotations


def render_report(repo_name: str, now: str, results: list[dict]) -> str:
    lines = [f"# architecture-scan — {repo_name} — {now}", "",
             f"{len(results)} candidate(s) processed.", ""]
    for r in results:
        lines.append(f"## {r['candidate']}  ({r['file']}, {r['lines']} lines, degree {r['degree']})")
        lines.append(f"- outcome: **{r['outcome']}** — {r['detail']}")
        lines.append(f"- recommendation: {r['recommendation']}")
        lines.append("")
    return "\n".join(lines)
