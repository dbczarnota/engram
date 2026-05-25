---
description: Tiered recall from the brain vault. Usage: /recall <query> [--include-archive]
---

Recall knowledge from the brain vault at `<BRAIN_PATH>`.

Query: $ARGUMENTS

Procedure (tiered — minimize tokens):
1. Read `_meta/index.md` and the headings (not full bodies) of files in `standards/` and `dashboards/`.
2. Pick only the pages whose one-line summary matches the query.
3. Read ONLY those full pages.
4. Exclude `archive/` unless the query contains `--include-archive`.
5. Answer, citing the vault pages you used (relative paths). If nothing matches, say so plainly —
   never invent. Do not load the whole vault.
