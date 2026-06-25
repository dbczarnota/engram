---
description: Summarize the current session into the active project's journal + capture new todos. Usage: /checkpoint
---

Write a checkpoint to the brain vault (`<BRAIN_PATH>`) for the CURRENT project.

1. Identify the project: read `_meta/project-map.json` and match the current working directory to a
   slug. If no match, ask me which project, or offer to create `projects/<slug>/` from
   `_meta/templates/project.md` and add the mapping.
2. Summarize THIS session in 5–10 concrete, terse bullets: decisions, changes, in-progress, blockers.
   Exclude routine chatter.
3. Prepend a dated entry (newest on top) to `projects/<slug>/journal.md`, using
   `_meta/templates/journal-entry.md`.
4. Extract deferred todos / ideas raised but not done → append to `projects/<slug>/todos.md` with
   `#deferred` or `#idea` and today's date. Skip anything already listed.
4b. Curate feature notes (no duplicates). From the files this session touched, find the matching
   feature note in `projects/<slug>/features/*.md` (overlap with each note's `files:` list); also
   check `projects/<slug>/features/_inbox/`.
   - Match found → show a diff and update that feature note's `## How it's built` (+ append new
     `commits`/`files`); do NOT create a second note.
   - No match but the session built a coherent feature → create
     `projects/<slug>/features/<name>.md` from `_meta/templates/feature.md` with graph frontmatter.
   - Nothing feature-worthy → skip. Keep `files:` as a single-line JSON array.
5. Show me the diff of the journal/todos changes (so I can see what was captured).
6. Commit AND push the checkpoint automatically — no need to ask. **Stage ONLY the files THIS
   checkpoint touched — never `git add -A`** (concurrent sessions may have unrelated unstaged work in
   the vault that must not be swept into this commit):
   `git -C "<BRAIN_PATH>" add "projects/<slug>/journal.md" "projects/<slug>/todos.md"` plus any feature
   note you created or updated under `projects/<slug>/features/` (add each such path explicitly).
   Then commit with a message like `checkpoint(<slug>): <one-line title>` and push the CURRENT branch:
   `git -C "<BRAIN_PATH>" push origin HEAD` (fast-forward only).
   The vault has a remote (`origin`); always push after committing.
   If the push is rejected (non-fast-forward) or there is no network, report it and stop — do NOT
   force-push.
