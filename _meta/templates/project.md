---
type: project
tags: [project]
status: active
date: {{date}}
links: []
---

# {{Project Name}}

**Repo:** `path\to\repo`
**Stack:**
**Status:** active

## What it is
One paragraph.

## Standards in use
- [[standards/...]]

## Observability
- logfire project: ` ` · db: ` ` (credentials live in the repo's own config, not here)

## Specs & plans

**Specs**
```dataview
LIST WHERE startswith(file.path, this.file.folder + "/specs/") SORT file.name DESC
```

**Plans**
```dataview
LIST WHERE startswith(file.path, this.file.folder + "/plans/") SORT file.name DESC
```
