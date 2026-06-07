---
description: Create/update a feature note, or review the features/_inbox draft queue. Usage: /feature [<name>]
---

Capture "as-built" knowledge for a feature. Input: $ARGUMENTS

**If $ARGUMENTS is empty, run INBOX REVIEW:**
1. Resolve the project via `_meta/project-map.json` from the cwd. List drafts in
   `projects/<proj>/features/_inbox/*.md`. If none, say so and stop.
2. For each draft show its body and ask me: promote, edit-then-promote, or discard.
3. On promote:
   - If the draft has `updates: <slug>`, merge its body into `projects/<proj>/features/<slug>.md`
     (refresh the relevant `##` section; do not duplicate content).
   - Else create `projects/<proj>/features/<name>.md` from `_meta/templates/feature.md`.
   - Fill the graph frontmatter from the work: `standards`/`lessons` (wikilinks to the
     standards/lessons actually used), `spec` (the driving spec note), `commits` (short SHAs),
     `files` (repo-relative paths touched — SINGLE-LINE JSON array, e.g. `files: ["a/b.py"]`).
   - `git rm` the draft.
4. On discard: `git rm` the draft.

**If $ARGUMENTS is a name (`/feature <name>`):**
1. Resolve the project from cwd. Create/append `projects/<proj>/features/<name>.md` from the template.
2. From the current branch/session, fill the three sections (What it does / How it's built / how a
   problem was solved) and the graph frontmatter (`standards`/`lessons`/`spec`/`commits`/`files`,
   `files` as a single-line JSON array).
3. Show the diff. Commit only if I say so.
