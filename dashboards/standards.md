---
type: meta
tags: [meta, dashboard]
status: active
date: 2026-05-25
---

# 📐 Standards

```dataview
TABLE WITHOUT ID file.link AS "Standard", date AS "updated"
FROM "standards"
WHERE type = "standard"
SORT file.name ASC
```
