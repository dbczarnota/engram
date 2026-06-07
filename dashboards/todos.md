---
type: meta
tags: [meta, dashboard]
status: active
date: 2026-05-25
---

# 📌 Todos (all projects + inbox)

Open checkboxes from every project's `todos.md`, the root `todos.md` inbox, and any
other note (excluding `archive/`, `specs/`, `plans/`). This stays on **Dataview** —
Bases aggregates notes, not checkbox lines, so it cannot reproduce this view.

```dataview
TASK
WHERE !completed
  AND !contains(file.folder, "archive")
  AND !contains(file.path, "/specs/")
  AND !contains(file.path, "/plans/")
GROUP BY file.folder
```

## Someday / maybe (`#idea` / `#deferred`)

Open todos tagged as ideas or deferred, sifted out from the active list above. Stays on
**Dataview** — it filters checkbox lines by their inline tag, which Bases cannot do.

```dataview
TASK
WHERE !completed AND (contains(tags, "#idea") OR contains(tags, "#deferred"))
  AND !contains(file.folder, "archive")
  AND !contains(file.path, "/specs/")
  AND !contains(file.path, "/plans/")
GROUP BY file.folder
```
