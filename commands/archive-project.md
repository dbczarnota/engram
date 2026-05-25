---
description: Move a finished project to archive/, excluded from recall + dashboards. Usage: /archive-project <slug>
---

Archive a project in the brain vault at `<BRAIN_PATH>`. Slug: $ARGUMENTS

1. Confirm `projects/<slug>/` exists. If not, list available projects and stop.
2. Move `projects/<slug>/` → `archive/<slug>/`.
3. Remove the project's entry from `_meta/project-map.json` and its line under `## Projects` in
   `_meta/index.md`.
4. Reminder: `/recall` and the dashboards exclude `archive/` by default (use `--include-archive` to reach it).
5. Show the diff. Commit only if I say so.
