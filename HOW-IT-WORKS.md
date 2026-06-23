# How this whole setup works (plain language)

There are **two separate systems** in **two separate places**. Keeping them straight is the key to
understanding everything else.

## 1. The brain vault — knowledge ACROSS projects

- **What:** project pages, standards, lessons, journals, deferred todos, research.
- **Where:** the `brain` git repo (this folder), pushed to GitHub.
- **Form:** plain markdown. Also an Obsidian vault (open it to see the graph/dashboards).
- **This is the thing you back up and version.** If your computer dies, `git clone` restores all your
  cross-project knowledge.

## How recall works (grep first, semantics optional)

`/recall` is **tiered** to keep token cost low and visible:

1. **Index tier** — read `_meta/index.md` (a one-line-per-page table of contents) and the headings of
   `standards/` + `dashboards/`. Cheap, almost always enough to know *which* page to open.
2. **Semantic tier (optional)** — if you set up `_meta/semantic/`, the query is embedded and matched by
   *meaning* against the vault's markdown (chunked by heading, stored in `sqlite-vec` + FTS5, fused with
   Reciprocal Rank Fusion). This catches paraphrases that share no keywords with the note. Without it,
   `/recall` simply falls back to grep.
3. **Read tier** — only the matched pages are read in full.

The semantic index is **gitignored and regenerable** (like the CRG code graph) — it's never the source of
truth; the markdown is. Rebuild any time with `python -m reindex`.

**Auto-recall (optional, on by default)** makes recall *proactive*: a `UserPromptSubmit` hook injects a tiny
"possibly relevant notes" hint on substantive prompts — FTS-first (most turns never import the embedder),
scoped to standards/lessons/decisions, silent when unsure, de-duped per session. Toggle/knobs live in
`_meta/engram.json`. It draws from the vault only — never code — so it stays complementary to CRG.

## 2. CRG (code-review-graph) — code structure INSIDE one project

- **What:** a map of one repo's code — classes, functions, imports, call graph — as a queryable graph,
  served to the agent over **MCP** (the agent calls it directly, like any tool).
- **Where:** `.code-review-graph/graph.db` (SQLite) **inside each project repo**. **NOT in brain.** Gitignored.
- **Form:** a per-repo graph DB + a global `code-review-graph` MCP server exposing query tools.
- **Regenerable:** derived from your code. Lose it and rebuild with `code-review-graph build` — no knowledge lost.

The brain only **points** to a project's graph; the DB rides along in the project repo.

## How CRG is built and kept fresh

- **Tooling:** installed once (`uv tool install code-review-graph`); the MCP server is registered user-scope
  and auto-detects the repo you're in.
- **Cost model:** parsing **code** uses tree-sitter locally = **0 tokens, free**. Semantic search uses a
  **local** embedding model (`all-MiniLM-L6-v2`, no API key).
- **First build:** `code-review-graph build` (AST → `graph.db`, uses `git ls-files` so node_modules is
  excluded) then `code-review-graph embed` (local embeddings → semantic search).
- **Auto-refresh on commit:** the post-commit hook (`hooks/install-crg-hook.ps1`) runs
  `code-review-graph update` (re-parses changed files) then a **self-heal prune** that strips any
  dependency / worktree nodes the Windows `update` path re-adds — so the graph stays app-only every commit.
- **So:** new functions enter the graph **when you commit them**. Embeddings aren't refreshed per-commit
  (too heavy); run `code-review-graph embed` periodically to index new nodes for semantic search.

## How the agent uses it day to day

- A directive in your global `CLAUDE.md` tells the agent to **consult CRG-MCP for structure & impact**:
  `query_graph` (callers/callees), `semantic_search_nodes` (find the code that does Y),
  `get_impact_radius` (blast-radius before an edit), `shortest_path` (A→B).
- **When it wins:** multi-hop / cross-file / architectural questions where flat grep+Read fails or
  hallucinates. The win is **precision and fewer tool-calls, not token savings** — for exact strings/config/
  logs, grep still wins.
- `/onboard-project` builds CRG (+ the auto-rebuild hook) for a repo that has none yet.

## The end-to-end loop

1. **Work in a project repo.** Commit as usual → CRG auto-updates + self-prunes (free, background).
2. **Ask the agent about the code** → it consults the project's CRG graph over MCP.
3. **Ask about cross-project things** ("how did we do auth", "like in the twins") → it consults the **brain
   vault** (standards / lessons / other project pages) via `/recall` or the CLAUDE.md pointer.
4. **At session end** → the capture hook writes a journal entry to the brain project page (if mapped).
5. **When you learn something reusable** → `/remember-standard` or `/remember-lesson` (explicit) puts it in
   brain so every future project benefits.

**brain (your knowledge) is the thing that must be backed up — and it already is, on GitHub.** The per-repo
`.code-review-graph/` DB is gitignored and rebuilt from code anytime.
