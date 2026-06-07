---
description: Seed feature notes for an existing project by distilling its wiki + specs + graphify graph into features/_inbox drafts for review. Usage: /backfill-features <slug | current>
---

Backfill feature notes for an EXISTING project (one that predates the feature-wiki system, so it has
no `features/` notes). Input: $ARGUMENTS (a project slug, or empty → resolve the current cwd).

**Everything goes to `features/_inbox/` as drafts — never write into `features/` directly.** You triage
with `/feature`.

1. **Resolve** the slug + repo path from `_meta/project-map.json` (arg or cwd). If
   `projects/<slug>/<slug>.md` does not exist, stop and suggest `/onboard-project` first (the project
   page + graphify must exist before backfilling features).
2. **Scaffold:** create `projects/<slug>/features/` and an empty `projects/<slug>/features/_inbox/.gitkeep`
   if missing.
3. **Gather sources (read-only):**
   - `projects/<slug>/<slug>.md` — its `##` sections are the primary feature candidates;
   - `projects/<slug>/specs/*.md` + `plans/*.md` — design intent;
   - the repo's `graphify-out/GRAPH_REPORT.md` — god-nodes + communities give code-level boundaries
     and the file groupings for `files:`. If absent, inspect the repo structure directly.
4. **Propose a candidate list** (feature name + one-line scope) and ask me which to draft. **Do not
   draft all of them** — only the features worth referencing; the rest accrete on-touch.
5. **For each chosen candidate**, write a draft `projects/<slug>/features/_inbox/<YYYY-MM-DD>-<name>.md`
   from `_meta/templates/feature.md`, filling:
   - the three sections (What it does / How it's built / How we solved <problem>) from the sources;
   - frontmatter graph keys: `standards`/`lessons` (wikilinks where evident), `spec` (the driving spec
     note if any), `commits` (`[]` unless obvious from journal/git), and **`files:` as a SINGLE-LINE
     JSON array** of the feature's repo-relative paths (from graphify god-nodes / the code area).
     Accurate `files:` is the point — it lets the capture curator MATCH and UPDATE this note later
     instead of creating a duplicate.
6. **Hand off:** tell me to review the inbox with `/feature` (promote / edit-then-promote / discard).
7. Show the diff. Commit only if I say so.

Principle: backfill only what you'll actually reference; accurate `files:` over volume.
