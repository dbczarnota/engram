---
description: Assess how the brain setup is actually performing over recent sessions, with honest conclusions + proposals. Read-only. Usage: /brain-health [days]
---

Run a read-only health check of the brain memory system. Input: $ARGUMENTS (optional window in days, default 30).

1. Run the metrics engine:
   `uv run --directory _meta/semantic --env-file _meta/semantic/.env python -m health_check $ARGUMENTS`
   (prints, over the window: auto-recall used/ignored/junk + top surfaced notes, capture
   auto-vs-manual, lesson/feature accretion, and `_inbox` backlog).
2. Read the printed metrics and write an **honest assessment** — what works, what doesn't — citing the
   numbers. Be candid; this is a review, not a status report.
3. Propose **concrete improvements** tied to the numbers, e.g.:
   - auto-recall still N% ignored → adjust packaging / scope / `tier2Min` / `minScore`;
   - K drafts stuck in `_inbox` → run `/vault-tidy`;
   - capture still mostly manual → check the Stop/SessionEnd hooks are firing.
   Do NOT implement them — propose only.
4. Offer to save the assessment as a dated note `research/brain-health-YYYY-MM-DD.md` (`type: research`).
   This skill mutates nothing else.
