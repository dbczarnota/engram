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

## Features
```base
filters:
  and:
    - file.inFolder(this.file.folder + "/features")
    - type == "feature"
views:
  - type: list
    name: Features
```

## Research

Research specific to this project. General / cross-project research → [[dashboards/research]].

```base
filters:
  and:
    - file.inFolder(this.file.folder + "/research")
    - type == "research"
views:
  - type: list
    name: Research
```

## Specs & plans

**Specs**
```base
filters:
  file.inFolder(this.file.folder + "/specs")
views:
  - type: list
    name: Specs
```

**Plans**
```base
filters:
  file.inFolder(this.file.folder + "/plans")
views:
  - type: list
    name: Plans
```
