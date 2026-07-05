# Implement the planned fix (behavior-preserving refactor)

Apply the SMALLEST change that realizes the plan below, then STOP. Behavior must not change.

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
- Edit ONLY the file(s) the issue is about; keep the diff minimal.
- Do NOT change public behavior, signatures, or outputs. No migrations/deploy/CI/Dockerfiles.
- Do NOT run tests, commit, push, merge, or deploy — just make the edit and stop.
- After editing, self-critique your own diff.

## Output
Return `{"applied": true|false, "self_critique": "<does the diff fully realize the plan? any risk / behavior change?>"}`.
