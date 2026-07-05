# Synthesize a refactor RFC

Three interface designs were produced for `{QUALIFIED_NAME}` (`{FILE}`). Compare them, recommend the
strongest, and propose a hybrid grafting the best elements. Then write a refactor RFC.

Designs (JSON): {PROPOSALS_JSON}

Return an object with exactly:
- `recommendation`: one line naming the chosen/hybrid approach.
- `rfc_markdown`: a full RFC with sections **Problem** (concrete pain, cite the code), **Solution
  (recommendation)**, **Alternatives considered** (a table of the 3 designs with each one's weakness),
  **Impact & risk** (blast radius, invariants to preserve, how to verify — existing tests must pass
  unchanged). Behavior-preserving. This is a decision document, not a diff.
