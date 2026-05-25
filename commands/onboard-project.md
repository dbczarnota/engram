---
description: Analyze a project repo and add it to the brain vault. Usage: /onboard-project <path | current>
---

Onboard a project into the brain vault at `<BRAIN_PATH>`.
Target: $ARGUMENTS (default: current working directory).

1. Resolve the repo root and pick a kebab-case slug.
2. Analyze the repo: README, package manifests (pyproject/package.json), top-level structure, its own
   CLAUDE.md if any, recent `git log`.
   **Graphify (auto):** if `graphify.enabled` is true in `_meta/engram.json` and `graphify` is on PATH —
   read `graphify-out/GRAPH_REPORT.md` for structure when it exists; **otherwise build it now, no manual
   step.** `graphify .` **hard-fails without an LLM key**, so first make `GEMINI_API_KEY` available (export it
   from `_meta/semantic/.env` if present). **If no key is found anywhere, tell the user plainly that the
   Graphify graph was skipped for lack of `GEMINI_API_KEY`** (set it and re-run `/onboard-project`) and grep
   the repo instead — never run `graphify .` keyless. With a key: run `graphify .`, then
   `graphify cluster-only .`, then install the auto-rebuild hook with
   `pwsh -NoProfile -Command ". '<BRAIN_PATH>\hooks\install-graphify-hook.ps1'; Install-GraphifyHook -RepoPath ."`
   (use **this**, not `graphify hook install` — the upstream hook silently no-ops on uv-tool/Windows installs),
   then read the report. If Graphify is disabled or not installed, grep the repo directly.
3. Create `projects/<slug>/<slug>.md` from `_meta/templates/project.md`: what it is, stack, status,
   build/test/lint commands, and observability coordinates (logfire project / db — **names only, never
   secrets**).
4. Create empty `projects/<slug>/journal.md`, `projects/<slug>/todos.md`, and `specs/` + `plans/` folders.
5. Add the repo path → slug mapping to `_meta/project-map.json` (so the capture hook recognizes it).
6. Propose CANDIDATE standards and lessons you noticed (patterns reused across projects, gotchas) as a
   numbered list for my explicit approval. **Do NOT write to `standards/` or `lessons/` without my OK.**
7. Add a one-line project summary under `## Projects` in `_meta/index.md`.
8. Show the diff. Commit only if I say so.
