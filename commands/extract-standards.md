---
description: Scan a project's superpowers specs/plans and propose cross-project standards. Usage: /extract-standards <path | current>
---

Extract reusable standards from a project's design history. Target: $ARGUMENTS (default: current dir).

1. Read `docs/superpowers/specs/*.md` and `docs/superpowers/plans/*.md` in the project, plus any ADRs in
   `<BRAIN_PATH>\projects\<slug>\decisions\`.
2. Identify recurring DECISIONS — choices that appear across multiple specs/projects, or that read like
   "how we always do X" (not one-off project specifics).
3. For each candidate, check `brain/standards/` for an existing match; note overlaps or conflicts.
4. Present a numbered list of proposed standards: the rule, why, and which spec(s) evidence it.
5. **On my explicit approval only**, write/update `brain/standards/` via `_meta/templates/standard.md`
   and add one-line summaries to `_meta/index.md`. Never auto-write.
6. Show diffs. Commit only if I say so.
