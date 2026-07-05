# Fix a failing check (code only)

A check in this repo is FAILING. Make the SMALLEST production-code change that makes THIS specific failure
pass, then STOP. Do NOT modify, weaken, or delete any test — fix the code.

## Failing check
- id: {ID}
- command: {COMMAND}
- detail: {SNIPPET}

## Feedback from a previous attempt (if any)
{FEEDBACK}

## Rules
- Edit production code only. Do NOT touch test files, migrations, deploy, CI, or Dockerfiles.
- Keep the diff minimal and localized. Do not fix unrelated things.
- Do NOT run tests, commit, push, or deploy — just make the edit and stop.
- After editing, self-critique: does it truly resolve this failure without breaking anything else?

## Output
Return `{"applied": true|false, "self_critique": "<does it resolve the failure? any risk of a NEW failure?>"}`.
