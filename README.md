# 🧠 Engram — a memory & knowledge vault for Claude Code

*The memory trace for your coding agent.*

**Engram is a plain-markdown, git-versioned memory system that gives Claude Code persistent, *controllable*
knowledge across all your projects — without burning context tokens.**

> *An engram is the physical trace a memory leaves behind. This is that trace for your agent — durable,
> inspectable, and yours.*

It is also an **Obsidian vault**: open the folder in Obsidian to browse the graph, dashboards, and notes.
Claude reads the same `.md` files via grep (and, optionally, semantic search) — so you get a visual wiki
for humans **and** cheap, on-demand recall for the agent, from one source of truth.

This repository is a **starter template**: clone it, run one wizard, and you have an empty, working Engram
vault of your own. The example standard and lesson shipped inside are meant to be deleted.

---

## Why I built this — and what I hit with claude-mem + Auto-Memory

I didn't set out to build a memory system. I was using **claude-mem** alongside Claude Code's built-in
**Auto-Memory**, and after a few weeks of real work across several projects, the same four problems kept
biting me:

1. **I couldn't see where my tokens went.** Auto-memory injected a few thousand tokens of "observation
   timeline" at the top of *every* session. I was hitting context limits and had no visibility into — or
   control over — what was being spent before I'd typed a word.
2. **It recalled the wrong things.** It would resurface a *completed* todo or an abandoned idea as if it
   were still live, then I'd waste turns correcting the agent's assumptions.
3. **It remembered chatter, not how I build.** It stored facts from conversations, but never *"this is how
   we do auth"* or *"this is the trap we hit with that library."* So across projects the same architectural
   decisions got re-litigated and solved five different ways.
4. **It was an opaque blob.** I couldn't open it, browse it, diff it, audit it, or fix a wrong memory by
   hand. I had to trust it, and it hadn't earned that.

The breaking point was my workflow. I work in a spec → plan → implement loop that produces a lot of design
docs, and **none of their conclusions were turning into anything reusable.** My memory tool was spending my
context budget to remind me of stale todos while quietly losing the one thing actually worth keeping: the
decisions.

**What I actually wanted:**

- An agent that **knows what I'm doing across projects** — and understands me when I say *"let's build this
  the way we did it in the twins."*
- A real **wiki I can open and browse** — a picture of my projects and how they connect, not a black box.
- **Deferred todos and mid-project ideas**, tracked and linked to the project they came from.
- **Lessons learned that stick**, so I never debug the same trap twice.
- **Standards the agent actually applies** — if we build agents a certain way in one project, we do it the
  same way in the next, instead of re-deciding it five different ways.
- To **not** have to memorize every conversation — just the conclusions worth keeping.
- **Low, visible token cost** — stop re-planning and re-speccing the same thing, and stop hitting limits
  because something invisible ate my context.
- A sense of **control** — plain text I can see, diff, and correct.
- And, because I use the **superpowers** spec/plan workflow: a way to **distill those specs and plans into
  standards**, so the time I spend designing pays off more than once.

So I made a deliberate bet — the opposite stance on every problem above: **plain markdown + git, read
on-demand and visibly, written cheaply and automatically.** A memory I can open in Obsidian, diff in `git`,
correct by hand, and that captures *standards and lessons*, not transcripts. That bet is Engram.

## The core principle: visible reads, automatic writes

The pain with agent memory is almost always on the **read** side — memory that injects itself *invisibly and
unconditionally* into every prompt. Engram's reads are **visible and bounded** instead:

- **On-demand by default** — you run `/recall`, or the agent greps the vault when it has a reason to.
- **Optional proactive auto-recall** — a `UserPromptSubmit` hook can surface a *tiny* hint (≤ ~200 tokens,
  only on substantive prompts, only when confident, de-duped per session, shown in the transcript). It's the
  deliberate opposite of a silent multi-thousand-token dump, and you can turn it off in `_meta/engram.json`.

**Writing**, on the other hand, can be automatic, because writing a markdown file costs zero session tokens
and is fully visible in a `git diff`. A session-end hook appends a short journal entry; you stay in control
of what becomes a durable *standard* or *lesson* (those are created only when you explicitly ask).

The result: low and **visible** token cost, full auditability (it's just text in git), and knowledge that
compounds instead of decaying.

## What you get

- **Standards** (`standards/`) — "how we always do X", applied across projects. Decide once, reuse forever.
- **Lessons** (`lessons/`) — hard-won, tech-specific gotchas. Never debug the same trap twice.
- **Per-project state** (`projects/<slug>/`) — what the project is, a `journal.md` of session summaries
  (newest on top), and `todos.md` for deferred ideas. Specs/plans and project-specific `research/` live
  here too, not in the code repo.
- **Research** (`research/` + `projects/<slug>/research/`) — write-ups and references you cite explicitly:
  general/cross-project research in the central catalog, single-project research under its project.
- **Dashboards + graph** (Obsidian Bases for projects/standards/research tables, Dataview for the todo
  aggregation) — a browsable picture of projects ↔ standards ↔ lessons ↔ research.
- **Archive** (`archive/`) — finished projects, excluded from recall so the active base stays small.
- **Semantic recall** (optional, `_meta/semantic/`) — concept-level search over the vault, so "how do we
  authenticate clients" finds a note titled "two-scheme API-key + JWT" even with zero shared keywords.
- **Auto-recall** (optional, on by default) — a proactive hook that surfaces a small "possibly relevant
  notes" hint on substantive prompts (scoped to standards/lessons/decisions), bounded and silent when
  unsure; toggle/tune in `_meta/engram.json`.

## How it compares

Honest positioning against other "memory for coding agents" approaches:

| Dimension | **Engram (this)** | claude-mem | Mem0 / Zep | Letta / MemGPT | basic-memory (MCP) |
|---|---|---|---|---|---|
| Store | **markdown + git** | SQLite + Chroma | hosted / vectors | memory blocks | markdown + SQLite |
| Read model | **on-demand + bounded proactive hint** | auto-injected each session | proactive injection | automatic | MCP query |
| Control / audit | **full (`git diff`)** | low | low | medium | good |
| Human view | **Obsidian graph + dashboards** | none | none | none | partial |
| Cross-project *standards* | **yes (the differentiator)** | no | no (stores facts) | no | no |
| Automatic memory extraction | **no** (explicit + journal) | yes | yes | yes | partial |
| Scale / multi-user | personal / solo | small | **strong** | medium | medium |
| Offline / no service | **yes** | yes | no | depends | yes |

**Where Engram wins:** control and auditability (plain text in git), transparent token cost (nothing
auto-injected), dual human+agent use (the same files power an Obsidian graph), and — the real
differentiator — distilling **engineering standards and lessons** that apply across projects. Most memory
tools store conversational facts; almost none capture "how we build things."

**Where Engram is weaker (by design or for now):**

- **No automatic memory extraction.** Mem0 and claude-mem mine your conversations for you; Engram relies on
  an explicit `/remember-standard` / `/remember-lesson` plus a session-end journal hook. It rewards a little
  discipline.
- **Auto-recall is young.** The proactive hint is v1 and unbenchmarked: its relevance threshold (`minScore`)
  may need per-vault tuning, and raw retrieval quality is mid-pack (contextual-retrieval blurbs and late
  chunking are deliberately deferred).
- **Windows-first.** The setup wizard and capture hook are PowerShell; macOS/Linux is a short manual port.
- **Personal scale.** grep + a small semantic index over your markdown is perfect for one person's vault;
  it is not a multi-user, team-scale memory backend.

**Choose Engram if** you're a solo developer working across many projects who wants control, auditability,
and reusable standards. **Look at Mem0/Zep instead if** you want zero-effort automatic memory or
team-scale, multi-user shared memory.

## Requirements

- [Claude Code](https://code.claude.com)
- The **[superpowers](https://github.com/obra/superpowers)** plugin (recommended) — Engram is built around
  its brainstorm → spec → plan → implement workflow, and `/extract-standards` reads the specs/plans it
  produces. Install: `/plugin marketplace add anthropics/claude-plugins-official` then
  `/plugin install superpowers@claude-plugins-official`. The wizard reminds you of this at the end.
- PowerShell 7+ (`pwsh`) — for the setup wizard and the capture hook (Windows-first; see *Non-Windows*)
- git
- [Obsidian](https://obsidian.md) (optional, for the graph/dashboards) + its **Dataview** community plugin
- [uv](https://docs.astral.sh/uv/) + a Gemini API key (optional, only for semantic `/recall`)
- *(Optional, and not set up by the wizard)* a **Logfire MCP** for `/logs` and a **Postgres MCP** for `/db`
  — wire these yourself only if you use those commands; everything else works without them.

## Quick start

```powershell
git clone <your-fork-url> brain
cd brain
pwsh -NoProfile -File .\setup.ps1            # or: -BrainPath "C:\abs\path\to\brain"
```

`setup.ps1` is an **interactive wizard**. It walks you through every step, and for each one it **shows the
exact change, asks before touching anything (`[Y/n/skip]`), and backs up any file it edits**:

1. Confirm the vault path.
2. Substitute the `<BRAIN_PATH>` placeholder with this folder's absolute path.
3. Junction the slash-commands into `~/.claude/commands`.
4. Register two hooks in `~/.claude/settings.json` (merged safely — your existing hooks are preserved): the
   `SessionEnd` capture hook and the `UserPromptSubmit` **auto-recall** hook (see below).
5. Set `autoMemoryEnabled: false` in `~/.claude/settings.json`.
6. Add a vault pointer to your global `~/.claude/CLAUDE.md` (a sentinel-bounded block, replaced in place on
   re-runs — never duplicated).
7. Optionally set up the AI add-ons (semantic search + the CRG code graph) behind a single Gemini-key prompt.

It is **idempotent**: re-run it any time — already-done steps report `[ok]` and change nothing. Use
**`-DryRun`** to preview the entire run without writing a single file.

A few things a script genuinely can't do are listed as **guided reminders** in the closing summary:

- Install the **superpowers** plugin (the brainstorm → spec → plan workflow Engram is built around).
- Disable any claude-mem-style **plugin** (a script can't toggle plugins).
- Open the folder in **Obsidian** and enable the **Dataview** community plugin (required for the todo
  dashboards). Optionally also install **File Hider** (`OA-file-hider`) to drop the infra folders from the
  file-explorer pane — see *Clean knowledge view in Obsidian* below.
- **Restart Claude Code**, then run `/recall test` to confirm the commands loaded.

## Testing it

The wizard's logic (safe JSON merge, the `CLAUDE.md` block, junction detection) is covered by standalone
PowerShell tests, and a dry run exercises the whole flow without writing anything:

```powershell
# unit tests — each prints "all passed"
pwsh -NoProfile -File .\setup.merge.test.ps1
pwsh -NoProfile -File .\setup.pointer.test.ps1
pwsh -NoProfile -File .\setup.junction.test.ps1

# full wizard, zero writes (point it at a throwaway config root)
pwsh -NoProfile -File .\setup.ps1 -DryRun -ConfigRoot "$env:TEMP\brain-dryrun"
```

If you enabled semantic search, its Python package has its own suite: `uv run --directory _meta\semantic pytest`.

## Commands

| Command | Purpose |
|---|---|
| `/recall <query>` | Tiered recall: `_meta/index.md` first, then an optional semantic tier, then drills into matching pages. Falls back to grep if semantic search isn't set up. |
| `/checkpoint` | Summarize the current session into the active project's `journal.md` + capture todos. |
| `/remember-standard <topic>` | Record a cross-project standard (explicit). Flags conflicts; never silent-overwrites. |
| `/remember-lesson <tech>` | Record a hard-won lesson. |
| `/vault-audit` | Lint: orphans, dead links, index drift, frontmatter gaps. |
| `/logs <focus>` | Investigate Logfire for the current project (if you use the Logfire MCP). |
| `/db <question>` | Query the project's database via a postgres MCP (if configured). |
| `/onboard-project <path>` | Analyze a repo and add it to the vault (auto-builds its CRG code graph when installed). |
| `/extract-standards <path>` | Scan a project's specs/plans, propose cross-project standards for approval. |
| `/feature` | Capture "as-built" knowledge for a shipped feature as a project feature note. |
| `/backfill-features <slug>` | Seed feature notes for an existing project by distilling its wiki + specs + graph. |
| `/archive-project <slug>` | Move a finished project to `archive/`, excluded from recall + dashboards. |
| `/vault-tidy` | Tidy the vault — detect, show the plan/diff, apply only on confirmation. |
| `/brain-health` | Read-only health check of the memory system. |
| `/backup-config` | Refresh a recovery snapshot of global Claude Code config into the vault. |

## Optional: Semantic search (concept-level `/recall`)

A small, self-contained semantic index over the vault's markdown lives in `_meta/semantic/`. It lets
`/recall` find notes by *meaning*, not just keywords. It's optional — without it, `/recall` uses the index
+ grep tiers.

How it works: markdown is chunked by heading, embedded with **Gemini** (behind a swappable `Embedder`
Protocol — point it at Voyage/Jina later), stored in **`sqlite-vec` + FTS5**, and queried as a hybrid
(vector + keyword) fused with Reciprocal Rank Fusion. The index is gitignored and regenerable — the
markdown is always the source of truth.

```powershell
cd _meta\semantic
copy .env.example .env          # then put your key in it (GEMINI_API_KEY=...)
uv run --env-file .env python -m reindex   # build the index (re-run after big edits)
```

Re-embedding is cached by content hash, so re-runs only embed changed chunks. To swap providers, implement
another `Embedder` in `embedder.py` and select it via `BRAIN_EMBED_PROVIDER`; a provider/dimension change is
detected and refuses a stale index until you reindex.

> **Semantic search vs CRG:** complementary, not the same engine. This indexes the vault's **knowledge
> across projects** (Gemini-embedded markdown); CRG maps **code structure inside** one repo (tree-sitter AST
> + a local code embedder). Different inputs, different stores.

### Auto-recall (proactive `/recall`)

With the semantic index built, a `UserPromptSubmit` hook turns recall **proactive**: on a substantive prompt
it injects a tiny "possibly relevant notes" hint so you don't have to remember to run `/recall`. It is
deliberately thrifty and quiet:

- **FTS-first** — a local keyword pass answers most prompts in ~0.3s and **never imports the embedder**;
  semantic search escalates only when keywords miss nothing strong.
- **Scoped** to `standards` / `lessons` / `decisions` (the "apply-this" knowledge) — never journals/todos or
  code; it is **disjoint from CRG** by design.
- **Silent when unsure** (a confidence threshold) and **de-duped per session** (a note is never injected
  twice), so it doesn't drift into the always-on token cost this project rejects.

Toggle and tune it in `_meta/engram.json` (`autoRecall.enabled` / `topN` / `minScore` / `tokenBudget` /
`scope`); the same file's `semantic.enabled` flag also gates the semantic layer (auto-recall escalation and
the `/recall` semantic tier). Trivial prompts ("ok", "run it") do nothing. *(CRG stays a separate per-repo
tool reached over MCP; `/onboard-project` builds it for a newly onboarded repo when `code-review-graph` is
installed.)*

## Optional: CRG (codebase knowledge graph over MCP)

[code-review-graph](https://github.com/tirth8205/code-review-graph) (CRG) turns a repo into a queryable code
graph (tree-sitter AST, parsed locally — **0 tokens, no API key**) and serves it to the agent over **MCP**.
It pairs well with this vault: CRG maps **code structure inside** a project, the vault holds **knowledge
across** projects. It indexes `git ls-files`, so `node_modules`/build dirs are excluded automatically.

`/onboard-project` does it for you: when `code-review-graph` is installed it builds the graph, computes local
embeddings, and installs an auto-rebuild post-commit hook — you never initialize CRG by hand and it stays
fresh on every commit. The manual sequence below is only for a repo you're not onboarding:

```powershell
uv tool install code-review-graph                # one-time: install the tool + register the MCP server
cd C:\path\to\your\repo
code-review-graph build                          # AST → .code-review-graph/graph.db (git ls-files; no key)
code-review-graph embed                          # local embeddings → semantic code search (no key)
pwsh -NoProfile -Command ". '<BRAIN_PATH>\hooks\install-crg-hook.ps1'; Install-CrgHook -RepoPath ."
```

> The post-commit hook runs `code-review-graph update` then a **self-heal prune** — on Windows the
> incremental `update` re-adds dependency/worktree files (it feeds backslash paths to a POSIX ignore
> matcher), so the prune keeps the graph app-only every commit.

The agent queries CRG over its MCP tools (`query_graph`, `semantic_search_nodes`, `get_impact_radius`,
`shortest_path`). See `HOW-IT-WORKS.md` for the full mental model of how the vault and CRG divide
responsibilities.

## Capture hook

`hooks/capture.ps1` runs at session end. If your current directory maps to a project in
`_meta/project-map.json`, it asks the (already-loaded) model to write a short journal entry. It honours a
`BRAIN_HOME` env var for testing and is best-effort — it never blocks session end. If your host doesn't fire
`SessionEnd` reliably, just use `/checkpoint` manually. Run `hooks/capture.test.ps1` and
`hooks/capture.integration.test.ps1` to verify the script.

## Structure

```
LICENSE              MIT
README.md            this file
HOW-IT-WORKS.md      the mental model (brain vs CRG code graph; how recall works)
CLAUDE.md            router for the agent when working inside the vault
Home.md              human landing page (open in Obsidian)
setup.ps1            the interactive install wizard
setup.lib.ps1        pure functions behind the wizard (unit-tested)
setup.*.test.ps1     wizard unit tests
_meta/               conventions, templates, recall index, project-map
_meta/engram.json    feature toggles + knobs (semantic, auto-recall)
_meta/semantic/      optional semantic-search index (Gemini + sqlite-vec); gitignored .env/.index
commands/            the slash-commands (junctioned to ~/.claude/commands)
hooks/               SessionEnd capture + UserPromptSubmit auto-recall hooks (+ tests)
standards/  lessons/  research/  projects/  archive/  dashboards/
```

## Clean knowledge view in Obsidian

Open the vault in Obsidian and you'd otherwise see the *infrastructure* too — `hooks/`, `commands/`,
`_meta/`, `.code-review-graph/`, the `setup.*` scripts. The shipped `.obsidian/app.json` already adds those to
Obsidian's **Excluded files** (`userIgnoreFilters`), so they drop out of search, the graph, and the quick
switcher — your recall surfaces stay knowledge-only with zero plugins.

Excluded files are still *dimmed-but-visible* in the file-explorer pane. To hide them from the tree
entirely, install the **File Hider** community plugin (`OA-file-hider`) and hide the same folders
(right-click → *Hide folder*). Its hidden list lives in the gitignored `.obsidian/plugins/`, so it's a
per-machine choice, not shipped.

## Non-Windows

The setup uses a Windows directory **junction** and a **PowerShell** hook. On macOS/Linux: replace the
junction with a symlink (`ln -s "$PWD/commands" ~/.claude/commands`), do the `settings.json` / `CLAUDE.md`
edits by hand (or port `setup.lib.ps1` — the logic is small), and port `hooks/capture.ps1` to a shell
script (~30 lines). The vault content and the semantic-search Python are OS-agnostic.

## Philosophy & credit

Distilled from real day-to-day use: markdown + git for control and auditability, Obsidian as the human
viewer, on-demand recall to keep token cost low and visible. Bring your own standards and lessons — the
shipped `standards/commit-messages.md` and `lessons/example-tool.md` are examples to delete.

## Contributing

Issues and PRs welcome. Keep the spirit: plain text, visible token cost, nothing auto-injected, the user
stays in control. If you port the setup/hook to macOS/Linux, a `setup.sh` + `capture.sh` pair would be a
very welcome contribution.

## License

[MIT](LICENSE) © 2026 Dominik Czarnota.
