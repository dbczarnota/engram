---
description: Analyze a project repo and add it to the brain vault. Usage: /onboard-project <path | current>
---

Onboard a project into the brain vault at `<BRAIN_PATH>`.
Target: $ARGUMENTS (default: current working directory).

1. Resolve the repo root and pick a kebab-case slug.
2. Analyze the repo: README, package manifests (pyproject/package.json), top-level structure, its own
   CLAUDE.md if any, recent `git log`. **If a Graphify graph exists (`graphify-out/GRAPH_REPORT.md`), read
   that for structure instead of grepping broadly.**
3. Create `projects/<slug>/<slug>.md` from `_meta/templates/project.md`: what it is, stack, status,
   build/test/lint commands, and observability coordinates (logfire project / db — **names only, never
   secrets**).
4. Create empty `projects/<slug>/journal.md` and `projects/<slug>/todos.md`.
5. Add the repo path → slug mapping to `_meta/project-map.json` (so the capture hook recognizes it).
6. Propose CANDIDATE standards and lessons you noticed (patterns reused across projects, gotchas) as a
   numbered list for my explicit approval. **Do NOT write to `standards/` or `lessons/` without my OK.**
7. Add a one-line project summary under `## Projects` in `_meta/index.md`.
8. Show the diff. Commit only if I say so.
