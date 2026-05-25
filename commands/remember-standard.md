---
description: Record a cross-project standard explicitly. Usage: /remember-standard <topic + the rule>
---

I am explicitly declaring a standard. Input: $ARGUMENTS

1. Choose `standards/<topic>.md` (kebab-case topic).
2. If it EXISTS: read it and CHECK FOR CONFLICTS with what I'm declaring. If the new rule contradicts
   existing content, STOP, show me the conflict side by side, and ask how to resolve. Never silently
   overwrite.
3. If new/no-conflict: write/update it from `_meta/templates/standard.md` (Rule, Rationale, Example,
   Applies to). Keep frontmatter valid.
4. If the page is new, add a one-line summary to `_meta/index.md` under `## Standards`.
5. Show the diff. Commit only if I say so.
