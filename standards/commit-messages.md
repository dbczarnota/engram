---
type: standard
tags: [standard, git, example]
status: active
date: 2026-05-25
links: []
---

# Standard: commit messages

**Rule:** Use Conventional Commits — `type(scope): summary`, imperative mood, ≤72-char subject.
Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

**Rationale:** machine-parseable history, easy changelogs, scannable `git log`.

**Example:**
```
feat(auth): add password reset flow
fix(api): handle empty results in search
```

**Applies to:** all repositories.

> This is an example shipped with the starter. Replace it with your own standards.
