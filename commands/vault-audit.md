---
description: Lint the brain vault — orphans, dead links, stale/contradictory content. Usage: /vault-audit
---

Audit the brain vault at `<BRAIN_PATH>`. REPORT only — fix nothing without asking.

Check and group findings:
1. **Orphans:** `.md` files not linked from any other note (ignore `_meta/templates/`, `_meta/backups/`, and `archive/`).
2. **Dead links:** `[[wikilinks]]` / markdown links whose target file does not exist.
3. **Stale:** notes with `status: active` and `date` older than 6 months; `journal.md` files untouched > 3 months.
4. **Missing index entries:** standards/lessons/projects not summarized in `_meta/index.md`.
5. **Contradictions:** standards that appear to conflict with each other.

Present as a grouped checklist. Then propose fixes and apply only the ones I approve.
