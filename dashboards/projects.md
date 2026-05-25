---
type: meta
tags: [meta, dashboard]
status: active
date: 2026-05-25
---

# 🗂 Projects

```dataview
TABLE WITHOUT ID link(file.link, regexreplace(file.folder, ".*/", "")) AS "Project", status, date AS "updated"
FROM "projects"
WHERE type = "project"
SORT file.folder ASC
```
