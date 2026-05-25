---
type: meta
tags: [meta, dashboard]
status: active
date: 2026-05-25
---

# 📌 Todos & Ideas (all projects)

```dataview
TASK
FROM "projects"
WHERE !completed
GROUP BY file.folder
```

## Deferred / idea notes
```dataview
LIST
FROM #deferred OR #idea
WHERE !contains(file.folder, "archive")
SORT date DESC
```
