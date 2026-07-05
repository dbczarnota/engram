from __future__ import annotations

_ORDER = ["prod-safe", "canary", "needs-human"]
_HEADS = {"prod-safe": "## prod-safe (recommended straight to prod — you decide)",
          "canary": "## canary (deploy behind a canary and watch)",
          "needs-human": "## needs-human (review before anything)"}


def render_integrate_report(repo_name: str, now: str, *, decisions: list[dict], bundles: list = ()) -> str:
    counts = {t: sum(1 for d in decisions if d.get("tier") == t) for t in _ORDER}
    fm = ["---", "type: integrate-report", f"project: {repo_name}", f"date: {now}", "read: false",
          *[f"{t}: {counts[t]}" for t in _ORDER], "---", ""]
    body = [f"# integrate-loop report — {repo_name}", "",
            "  ·  ".join(f"{t}: {counts[t]}" for t in _ORDER), ""]
    if bundles:
        body += ["", "## Bundles"]
        for b in bundles:
            branch = b.get("branch") or "(none — nothing shippable)"
            body.append(f"- {b.get('tier')}: `{branch}` — included {b.get('included')}, "
                        f"pulled {b.get('pulled')}, conflicts {b.get('conflicts')}")
    for t in _ORDER:
        rows = [d for d in decisions if d.get("tier") == t]
        if not rows:
            continue
        body += ["", _HEADS[t]]
        for d in rows:
            body.append(f"- [{d.get('dimension')}] `{d.get('branch')}` — {d.get('rationale')}  "
                        f"({d.get('fingerprint')})")
    body += ["", "> integrate-loop never merges or deploys. You are the gate — pick per fix or per bundle."]
    return "\n".join(fm + body) + "\n"
