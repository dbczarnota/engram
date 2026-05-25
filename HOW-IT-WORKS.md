# How this whole setup works (plain language)

There are **two separate systems** in **two separate places**. Keeping them straight is the key to
understanding everything else.

## 1. The brain vault — knowledge ACROSS projects

- **What:** project pages, standards, lessons, journals, deferred todos, research.
- **Where:** the `brain` git repo (this folder), pushed to GitHub.
- **Form:** plain markdown. Also an Obsidian vault (open it to see the graph/dashboards).
- **This is the thing you back up and version.** If your computer dies, `git clone` restores all your
  cross-project knowledge.

## 2. Graphify — code structure INSIDE one project

- **What:** a map of one repo's code — classes, functions, imports, call graph — as a queryable graph.
- **Where:** `graphify-out/` **inside each project repo** (e.g. `myproject/graphify-out/`). **NOT in brain.**
- **Form:** `graph.json` (the graph), `GRAPH_REPORT.md` (human/AI-readable summary), `graph.html` (click-around viewer).
- **Regenerable:** it's derived from your code. Lose it and you rebuild it with one command — no knowledge lost.

The brain only **points** to a project's graph (the project page says "graph lives here"). The graph itself
rides along in the project repo.

## How Graphify is built and kept fresh

- **Tooling:** installed once (`uv tool install graphifyy --with openai`), then `graphify install` registers
  a `/graphify` skill so the agent knows to use it.
- **Cost model:** parsing **code** uses tree-sitter locally = **0 tokens, free**. Only **docs/markdown** go
  through an LLM for a semantic pass (small, ~cents per project, needs an LLM API key in the environment).
- **First build:** `graphify .` (AST + semantic) then `graphify cluster-only .` (writes the report + HTML).
- **Auto-refresh on commit:** `graphify hook install` adds a git **post-commit** hook. Every commit
  re-parses the **changed files** (code only, free, in the background) and updates `graph.json`. A
  **post-checkout** hook refreshes on branch switches.
- **So:** new functions enter the graph **when you commit them** — then the agent sees them on the next
  `/graphify` query. Uncommitted code isn't in the graph yet; run `graphify update .` (free) to refresh
  by hand. The semantic/doc layer only updates on a full `graphify .`.

## How the agent uses it day to day

- `/graphify` (skill) + a directive in your global `CLAUDE.md` tell the agent: **consult the graph before
  grepping**. Querying `graph.json` (~280 tokens) or reading `GRAPH_REPORT.md` beats reading 40 files.
- `/onboard-project` reads a project's `GRAPH_REPORT.md` instead of scanning the whole codebase.
- Net effect: cheaper, faster navigation of large codebases; the agent answers "where is X / what calls Y /
  what's the architecture" from the graph.

## The end-to-end loop

1. **Work in a project repo.** Commit as usual → the graph auto-updates (free, background).
2. **Ask the agent about the code** → it consults the project's Graphify graph.
3. **Ask about cross-project things** ("how did we do auth", "like in the twins") → it consults the **brain
   vault** (standards / lessons / other project pages) via `/recall` or the CLAUDE.md pointer.
4. **At session end** → the capture hook writes a journal entry to the brain project page (if mapped).
5. **When you learn something reusable** → `/remember-standard` or `/remember-lesson` (explicit) puts it in
   brain so every future project benefits.

## Should you commit `graphify-out/` to git?

It lives in the **project** repo, and it's **regenerable from code**, so this is a per-project choice:

- **Gitignore it (recommended default):** keeps project repos clean; no churn from `graph.json` changing on
  every commit; rebuild anytime with `graphify .`. Your *knowledge* is safe in brain regardless.
- **Commit it:** versions the graph and gives instant recovery without a rebuild; Graphify ships a git
  merge-driver for `graph.json` so parallel commits don't conflict. Costs repo size + noisier diffs.

Either way, **brain (your knowledge) is the thing that must be backed up — and it already is, on GitHub.**
