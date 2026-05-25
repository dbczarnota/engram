---
description: Investigate logs/traces in Logfire for the current project. Usage: /logs <what to look for>
---

Investigate Logfire for the current project. Focus: $ARGUMENTS

1. Use the logfire MCP tools (`mcp__logfire__query_run`; `query_schema_reference` only if you need the full
   schema). Logfire authenticates via OAuth — if it's not connected, tell me to run `/mcp` to log in.
2. Write SQL (Apache DataFusion dialect) against records/spans. **Always include a `LIMIT`.** Default to a
   recent time window (e.g. last 1–24h) unless I specify otherwise.
3. Hunt for what I asked about — errors, exceptions, slow spans, specific attributes. Inspect span
   hierarchy / attributes rather than guessing.
4. Summarize findings concisely (relevant trace/span attributes, counts, timings) and propose the likely
   cause. Don't dump large raw result sets — distill.
