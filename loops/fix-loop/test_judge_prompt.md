# Is this failing test WRONG? (adversarial, read-only)

A regression/verify check is failing. A code fix has already been attempted and could NOT make it pass
without changing the test. Decide, skeptically, whether the TEST ITSELF encodes the WRONG expected
behaviour — i.e. it asserts something the production code should NOT do — versus the code being genuinely
buggy.

## Failing check
- id: {ID}
- command: {COMMAND}
- detail: {SNIPPET}

## Rules
- Read only. Do NOT edit anything.
- Default to `test-ok`. Return `test-wrong` ONLY if you are convinced, from reading the test AND the code
  it exercises, that the test's expectation is incorrect (not merely that the code is hard to fix).
- Changing a test to make it pass is dangerous — the bar for `test-wrong` is high.

## Output
Return `{"verdict": "test-wrong" | "test-ok", "justification": "<why, grounded in the test and the code>"}`.
