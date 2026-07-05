# Implement the smallest fix that makes the regression test pass

A regression test that reproduces the bug already exists and currently FAILS. Implement the SMALLEST
production-code change that makes it pass, then STOP. Do not weaken or delete the test.

## Issue
- dimension: {DIMENSION}
- file: {FILE}
- claim: {SUMMARY}

## Plan
- root_cause: {ROOT_CAUSE}
- approach: {APPROACH}
- justification: {JUSTIFICATION}

## Feedback from the previous attempt (if any)
{FEEDBACK}

## Rules
- Edit production code to fix the bug; do NOT edit, weaken, or delete the regression test.
- Keep the diff minimal and within the file(s) the bug is about. No migrations/deploy/CI/Dockerfiles.
- Do NOT run tests, commit, push, or deploy — just make the edit and stop.
- After editing, self-critique your diff: does it address the root cause? any risk / new failure?

## Output
Return `{"applied": true|false, "self_critique": "<does the fix address the root cause? any risk?>"}`.
