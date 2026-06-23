---
description: Analyze a project repo and add it to the brain vault. Usage: /onboard-project <path | current>
---

Onboard a project into the brain vault at `<BRAIN_PATH>`.
Target: $ARGUMENTS (default: current working directory).

1. Resolve the repo root and pick a kebab-case slug.
2. Analyze the repo: README, package manifests (pyproject/package.json), top-level structure, its own
   CLAUDE.md if any, recent `git log`.
   **CRG (code-review-graph, auto, keyless):** if `code-review-graph` is on PATH, build the fast code-lookup
   graph: `code-review-graph build` (AST → `.code-review-graph/graph.db`, uses `git ls-files` so node_modules
   is excluded) then `code-review-graph embed` (local `all-MiniLM-L6-v2`, no API key — enables semantic code
   search). Install the auto-rebuild + self-heal-prune hook with
   `pwsh -NoProfile -Command ". '<BRAIN_PATH>\hooks\install-crg-hook.ps1'; Install-CrgHook -RepoPath ."` (the
   hook prunes the per-commit `update` re-pollution on Windows). The CRG **MCP server is registered globally**
   (user-scope, auto-detects the repo), so once the graph exists its tools (`query_graph`,
   `semantic_search_nodes`, `get_impact_radius`, `shortest_path`) work in this repo. CRG gitignores
   `.code-review-graph/` itself. If `code-review-graph` is not installed, grep the repo directly.
3. Create `projects/<slug>/<slug>.md` from `_meta/templates/project.md`: what it is, stack, status,
   build/test/lint commands, and observability coordinates (logfire project / db — **names only, never
   secrets**).
4. Create empty `projects/<slug>/journal.md`, `projects/<slug>/todos.md`, and `specs/` + `plans/` +
   `features/` folders, plus an empty `projects/<slug>/features/_inbox/.gitkeep` (the feature-draft queue).
5. Add the repo path → slug mapping to `_meta/project-map.json` (so the capture hook recognizes it).
6. Propose CANDIDATE standards and lessons you noticed (patterns reused across projects, gotchas) as a
   numbered list for my explicit approval. **Do NOT write to `standards/` or `lessons/` without my OK.**
7. Add a one-line project summary under `## Projects` in `_meta/index.md`.
8. Show the diff. Commit only if I say so.
