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
5. Show me the diff. Do NOT commit unless I say so.
