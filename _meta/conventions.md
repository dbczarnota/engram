---
type: meta
tags: [meta, conventions]
status: active
date: 2026-05-25
---

# Vault Conventions

This vault is the single source of truth for cross-project knowledge. It is read by Claude Code
**on demand** (grep/Read) — nothing here is auto-injected into sessions.

## Core principle: automatic WRITE, visible on-demand READ
- Capture (journals, todos) may be written semi-automatically.
- Recall is on-demand by default (`/recall`, grep, or the pointer in global `~/.claude/CLAUDE.md`).
- Optional **auto-recall** adds a *bounded, visible* proactive hint (toggle/knobs in `_meta/engram.json`) —
  it never silently injects large context.

## Folders
- `projects/<slug>/` — one folder per project: `<slug>.md` (what/stack/status), `journal.md`
  (session summaries, newest on top), `todos.md` (deferred todos & ideas), `specs/` + `plans/` (superpowers design docs — kept here, NOT in the project repo), `decisions/` (ADRs).
- `standards/` — cross-project rules ("how we always do X"). Living documents.
- `lessons/` — cross-project gotchas, one file per tech. Never solve the same problem twice.
- `research/` — saved research outputs / papers, referenced explicitly.
- `archive/` — finished projects, excluded from recall & dashboards by default.
- `dashboards/` — Dataview views for humans.
- `_meta/` — conventions, templates, the recall index, and the project-path map.

## ADR vs Standard
- **ADR** (`projects/<slug>/decisions/`): why we decided X *in this project*, at one moment. Frozen;
  supersede with a new ADR rather than editing.
- **Standard** (`standards/`): how we do X *across all projects*. Living; update in place.
- ADRs that recur across projects are promoted to standards **only on explicit approval**.

## Frontmatter (required on every note)
`type` (project|journal|adr|standard|lesson|research|meta), `tags` (list), `status`
(active|archived|draft|superseded), `date` (YYYY-MM-DD), `links` (list of [[wikilinks]]).

## Tags
- `#deferred` — a todo postponed for later.
- `#idea` — an idea raised during work, not yet committed to.
- `#blocked` — waiting on something external.

## Writing standards & lessons
Created **only when the user explicitly asks** ("this is our standard…", "save this lesson…").
Never inferred silently.
