---
description: Record a lesson learned (tech gotcha) explicitly. Usage: /remember-lesson <tech>: <the lesson>
---

I am explicitly recording a lesson. Input: $ARGUMENTS

**If $ARGUMENTS is empty, run INBOX REVIEW first:**
1. List drafts in `lessons/_inbox/*.md`. If none, say so and stop.
2. For each draft, show its body and ask me: promote, edit-then-promote, or discard.
3. On promote: append/create `lessons/<tech>.md` (kebab tech from the draft's `tech:`), add a
   `## <tech>` section with How to spot it / The trap / The fix, then `git rm` the draft.
4. Ensure `lessons/README.md` and `_meta/index.md` list this tech (add a one-line entry if missing).
5. Add a backlink: in the promoted lesson's frontmatter `links:`, include `[[projects/<source_project>/<source_project>]]`.

**If $ARGUMENTS is provided (`<tech>: <the lesson>`):**
1. Choose `lessons/<tech>.md` (kebab-case). Append if it exists, create from `_meta/templates/lesson.md` if not.
2. Capture: How to spot it / The trap / The fix. Be specific enough to recognize next time.
3. Ensure `lessons/README.md` and `_meta/index.md` list this tech.
4. Show the diff. Commit only if I say so.
