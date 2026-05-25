---
type: meta
tags: [meta, dashboard]
status: active
date: 2026-05-25
---

# 🗂 Projects

```dataview
TABLE status, date AS "updated"
FROM "projects"
WHERE type = "project"
SORT date DESC
```
