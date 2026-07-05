# Write a regression test that reproduces the bug (NO fix yet)

Write ONLY a failing regression test that reproduces the bug below. Do NOT change any production code —
the test must FAIL against the current (unfixed) code, proving it reproduces the bug.

## Issue
- dimension: {DIMENSION}
- file: {FILE}
- claim: {SUMMARY}

## Do
- Read the relevant source to understand the bug.
- Add a test (in the repo's existing test layout — a `test_*.py` under the tests dir, or next to the
  code following the project's convention) that FAILS because of this bug.
- State the root cause, at least two fix approaches you considered, and which you will implement next
  (with a one-paragraph justification). Do NOT implement the fix now.

## Rules
- Edit ONLY test files. Do NOT touch production code, migrations, deploy, CI, or Dockerfiles.
- Do NOT run tests, commit, push, or deploy — just write the test and stop.

## Output
Return `{"root_cause": "...", "approach": "...", "alternatives": "...", "justification": "..."}`.
