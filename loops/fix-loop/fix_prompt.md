# Fix task (single finding, minimal, behavior-preserving)

Apply the SMALLEST change that resolves the issue below, then STOP. Do not refactor anything else.
This is a behavior-preserving refactor — the code's observable behavior must not change.

## Issue
- dimension: {DIMENSION}
- file: {FILE}
- claim: {SUMMARY}

## Rules
- Edit ONLY the file(s) the issue is about; keep the diff minimal.
- Do NOT change public behavior, signatures, or outputs.
- Do NOT touch migrations, deploy manifests, CI, or Dockerfiles.
- Do NOT run tests, commit, push, merge, or deploy — just make the edit and stop.
- If you cannot make a safe minimal fix, make NO change.

## Output
Return `{"applied": true|false, "summary": "<one line: what you changed, or why not>"}`.
