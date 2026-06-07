---
description: Deliberate vault cleanup — archive done-todos, triage inboxes, fix dead links/config, prune state. Detect→confirm→apply. Usage: /vault-tidy
---

Tidy the brain vault. Each section: **detect → show the plan/diff → apply only on my confirmation.**
Convention: ARCHIVE, never delete (the only hard delete is gitignored runtime state).

1. **Archive done-todos (≥30 days).** For each `projects/<slug>/todos.md`: find checked `[x]` items
   whose in-text date (e.g. `(2026-05-05)` or `2026-05-05`) is older than 30 days. Move them to
   `projects/<slug>/todos-archive.md` (create with a `# <slug> — Todos Archive` heading if absent),
   newest-first. Items with no readable date, or newer than 30 days, stay. Show the diff before moving.
2. **Triage `_inbox`.** List drafts in `lessons/_inbox/*.md` and every
   `projects/*/features/_inbox/*.md`, with their `date:`/age. For each, offer: promote (hand off to
   `/remember-lesson` or `/feature`) or discard (`git rm`).
3. **Lint + fix dead links/config.** Run the same detection as `/vault-audit` (dead wikilinks, orphan
   notes, `_meta/index.md` drift, dead config entries such as a `scope` folder that does not exist).
   Propose concrete fixes and apply only the ones I approve.
4. **Prune state.** Delete `_meta/state/session-*.json` older than 7 days (gitignored runtime — safe
   immediate delete). For the recall-log analysis, point me at `/brain-health`.

Finally, show a summary of what changed and commit per the vault rules (commit locally; do NOT push
unless I ask).
