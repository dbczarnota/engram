---
description: Tiered recall from the brain vault. Usage: /recall <query> [--include-archive]
---

Recall knowledge from the brain vault at `<BRAIN_PATH>`.

Query: $ARGUMENTS

Procedure (tiered — minimize tokens):
1. Read `_meta/index.md` and the headings (not full bodies) of files in `standards/` and `dashboards/`.
2. Semantic tier — **only if `_meta/engram.json` has `semantic.enabled` ≠ false** (if disabled, skip to
   step 3 and rely on grep). Run semantic search to get concept-level candidates (paraphrases grep misses):
   ```
   uv run --directory "<BRAIN_PATH>\_meta\semantic" --env-file "<BRAIN_PATH>\_meta\semantic\.env" python -X utf8 -c "import sys; from query import search; from pathlib import Path; [print(f'{h.score:.3f}  {h.path}  ::  {h.heading_path}') for h in search(Path(r'<BRAIN_PATH>'), sys.argv[1], top_n=8)]" "$ARGUMENTS"
   ```
   - On `IndexMismatch` or a missing DB, tell the user to run the reindex first
     (`uv run --directory "...\_meta\semantic" --env-file "...\_meta\semantic\.env" python -m reindex`),
     then fall back to grep for this query.
3. Combine candidates: pages matched by the index summaries (step 1) + the top semantic hits (step 2).
4. Read ONLY those full pages.
5. Exclude `archive/` unless the query contains `--include-archive`.
6. Answer, citing the vault pages you used (relative paths). If nothing matches, say so plainly —
   never invent. Do not load the whole vault.
