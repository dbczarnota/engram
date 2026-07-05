# Plan a fix (behavior-preserving refactor)

A previous minimal attempt to fix the issue below FAILED its check. Do NOT edit any code now — plan a
better fix. Read the relevant source and think it through.

## Issue
- dimension: {DIMENSION}
- file: {FILE}
- claim: {SUMMARY}

## Produce
- root_cause: what actually causes this (one or two sentences, grounded in the code you read).
- approach: the fix you will make (behavior-preserving — the code's observable behavior must not change).
- alternatives: at least one other approach you considered.
- justification: why your chosen approach is better than the alternative(s).

## Rules
- Read only. Do NOT edit, run, commit, push, or deploy.
- The fix must be minimal and stay within the file(s) the issue is about. No migrations/deploy/CI.

## Output
Return `{"root_cause": "...", "approach": "...", "alternatives": "...", "justification": "..."}`.
