# Assess a fix's release risk (recommend a tier)

A fix has landed on branch `{BRANCH}`. Judge from the diff shown below and the context below,
then recommend the SAFEST accurate release tier. You may make it SAFER than the floor; you may NOT make
it bolder (a bolder choice will be ignored).

## Context
- finding: {SUMMARY}
- dimension: {DIMENSION}
- deterministic signals: {SIGNALS}
- deterministic floor (the boldest allowed): {FLOOR}

## Diff
```
{DIFF}
```

You may also Read the changed files (read-only) for additional context.

## Tiers (safest → boldest)
- needs-human: a human must review before anything (risk, sensitivity, or you are unsure).
- canary: safe to deploy behind a canary and watch; not obviously prod-safe.
- prod-safe: a small, behavior-preserving, test-covered mechanical change safe to ship straight to prod.

## Rules
- Read only. Do NOT edit, run, commit, or deploy.
- Prefer the SAFER tier when uncertain. Demote below the floor if you see a real risk the rules missed
  (a subtle behavior change, an untested edge, hidden coupling, a security/tenant implication).
- Justify concretely (what to watch on canary; why a human is needed).

## Output
Return `{"tier": "prod-safe" | "canary" | "needs-human", "rationale": "<one paragraph, concrete>"}`.
