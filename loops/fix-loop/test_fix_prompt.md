# Correct a wrong test (test file ONLY)

An independent review judged that the failing test below encodes the WRONG expected behaviour. Correct the
TEST so it asserts the RIGHT behaviour, then STOP. Do NOT change any production code.

## Failing check
- id: {ID}
- command: {COMMAND}
- detail: {SNIPPET}

## Why the test is considered wrong
{JUSTIFICATION}

## Feedback from the previous attempt (if any)
{FEEDBACK}

## Rules
- Edit ONLY the test file the failing check lives in. Do NOT touch production code, other tests, or config.
- Make the smallest change that corrects the expectation. Do NOT delete the test or weaken it to a no-op
  (e.g. `assert True`) — it must still meaningfully assert the corrected behaviour.
- Do NOT run tests, commit, push, or deploy.

## Output
Return `{"applied": true|false, "self_critique": "<does the corrected test assert the RIGHT behaviour?>"}`.
