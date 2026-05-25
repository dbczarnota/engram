---
description: Record a lesson learned (tech gotcha) explicitly. Usage: /remember-lesson <tech>: <the lesson>
---

I am explicitly recording a lesson. Input: $ARGUMENTS

1. Choose `lessons/<tech>.md` (kebab-case tech name). Append if it exists, create from
   `_meta/templates/lesson.md` if not.
2. Capture: How to spot it / The trap / The fix. Be specific enough to recognize next time.
3. Ensure `lessons/README.md` lists this tech (add a one-line entry if missing).
4. Show the diff. Commit only if I say so.
