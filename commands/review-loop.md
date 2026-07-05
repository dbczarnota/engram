---
description: Run the review-loop on a repo — code review + auto-fix in an isolated worktree, report to the vault. Usage: /review-loop <repo-path> [--iter N]
---

Run the review-loop against `$ARGUMENTS` (a repo path; default: current repo root).

Invoke the runner (run from `<BRAIN_PATH>/loops/review-loop`):

```
uv run --no-project python __main__.py <repo-path> [--iter N]
```

The runner: validates the repo's `.reviewloop.yml`
(refuses if absent), creates an isolated worktree, runs review→fix→verify for the bug-hunt
dimension up to `max_iter`, and writes a report to the repo's configured `report_dir`.
It never merges, pushes, or deploys. After it finishes, summarize the report path and the
auto_fixed / report_only counts for me.
