---
description: Query the current project's PostgreSQL via the postgres MCP. Usage: /db <question or query>
---

Query the current project's database via the postgres MCP. Request: $ARGUMENTS

1. Use the postgres MCP tools. The server is configured per-project (local scope) — if it's not connected,
   tell me (it may need the project's port-forward / credentials running).
2. Prefer read-only `SELECT`s. Inspect the schema first (`information_schema`, table list) before guessing
   column names.
3. **Always `LIMIT`** result sets.
4. If the request implies a write, UPDATE, DELETE, or DDL — **STOP and confirm with me first.** Never run
   destructive SQL without explicit approval.
5. Summarize the answer and show the exact query you ran.
