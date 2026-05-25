# brain — a memory & knowledge vault for Claude Code

A lightweight, **plain-markdown + git** memory system that gives Claude Code persistent, *controllable*
knowledge across all your projects — without burning tokens.

It is also an **Obsidian vault**: open the folder in Obsidian to browse the graph, dashboards, and notes.
Claude reads the same `.md` files via grep — so you get a visual wiki for humans **and** cheap,
on-demand recall for the agent, from one source of truth.

## Core principle: automatic WRITE, on-demand READ

The usual pain with agent memory is automatic *reading* — tools that inject thousands of tokens into
every session. Here, recall is **on-demand only** (you run `/recall`, or the agent greps when it has a
reason to). Capture can be automatic (a session-end hook writes a journal entry), because writing a
markdown file costs no session tokens and is fully visible in a git diff.

## What it gives you

- **Standards** (`standards/`) — "how we always do X", applied across projects. No re-litigating decisions.
- **Lessons** (`lessons/`) — hard-won gotchas, one per tech. Never solve the same problem twice.
- **Per-project state** (`projects/<slug>/`) — what it is, a `journal.md` of session summaries, and
  `todos.md` for deferred ideas.
- **Research** (`research/`) — saved write-ups you reference explicitly.
- **Dashboards** + **graph** (via Obsidian Dataview) — a browsable picture of your projects and their links.
- **Archive** (`archive/`) — finished projects, excluded from recall so the active base stays small.

## Prerequisites

- [Claude Code](https://code.claude.com)
- PowerShell 7+ (`pwsh`) — for the setup script and the capture hook (Windows-first; see Non-Windows below)
- git
- [Obsidian](https://obsidian.md) (optional, for the graph/dashboards) + its **Dataview** community plugin

## Quick start

```powershell
git clone <your-fork-url> brain
cd brain
pwsh -NoProfile -File .\setup.ps1            # or: -BrainPath "C:\abs\path\to\brain"
```

`setup.ps1` substitutes the `<BRAIN_PATH>` placeholder with this folder's absolute path and installs the
slash-commands globally (a junction at `~/.claude/commands`). It then prints the remaining manual steps:

1. **Register the capture hook** in `~/.claude/settings.json`:
   ```json
   "hooks": {
     "SessionEnd": [
       { "hooks": [ { "type": "command", "command": "pwsh -NoProfile -File \"C:\\abs\\path\\to\\brain\\hooks\\capture.ps1\"" } ] }
     ]
   }
   ```
2. **Disable competing memory** (recommended) in `~/.claude/settings.json`:
   ```json
   "autoMemoryEnabled": false
   ```
   and disable any claude-mem-style plugin. (This system replaces them, with control + visibility.)
3. **Add the vault pointer** to your global `~/.claude/CLAUDE.md` so the agent knows the vault exists:
   ```markdown
   ## Knowledge Vault
   A knowledge vault lives at `C:\abs\path\to\brain` (git repo + Obsidian vault); single source of truth
   for standards, lessons, project state, research.
   - Before designing/building, consult `brain/standards/` and `brain/lessons/` — grep, don't load wholesale. Use `/recall`.
   - When I reference another project, grep `brain/projects/`.
   - Create standards/lessons ONLY when I explicitly say so (`/remember-standard`, `/remember-lesson`).
   - Consult the vault before answering when I reference past decisions, "how we did X", or another project — you don't need me to type /recall.
   ```
4. **Open the folder in Obsidian**, enable the **Dataview** plugin (Settings → Community plugins).
5. **Restart Claude Code**, then run `/recall test` to confirm the commands load.

## Commands

| Command | Purpose |
|---|---|
| `/recall <query>` | Tiered recall: reads `_meta/index.md` first, drills into matching pages only. |
| `/checkpoint` | Summarize the current session into the active project's `journal.md` + capture todos. |
| `/remember-standard <topic>` | Record a cross-project standard (explicit). Flags conflicts, never silent-overwrites. |
| `/remember-lesson <tech>` | Record a hard-won lesson. |
| `/vault-audit` | Lint: orphans, dead links, index drift, frontmatter gaps. |
| `/logs <focus>` | Investigate Logfire for the current project (if you use Logfire MCP). |
| `/db <question>` | Query the project's database via a postgres MCP (if configured). |

## Capture hook

`hooks/capture.ps1` runs at session end. If your current directory maps to a project in
`_meta/project-map.json`, it asks the (already-loaded) model to write a short journal entry. It honours a
`BRAIN_HOME` env var for testing and is best-effort — it never blocks session end. If your host doesn't
fire `SessionEnd` reliably, just use `/checkpoint` manually. Run `hooks/capture.test.ps1` and
`hooks/capture.integration.test.ps1` to verify the script.

## Structure

```
CLAUDE.md            router for the agent when working inside the vault
Home.md              human landing page (open in Obsidian)
_meta/               conventions, templates, recall index, project-map
commands/            the slash-commands (junctioned to ~/.claude/commands)
hooks/               session-end capture hook + tests
standards/  lessons/  research/  projects/  archive/  dashboards/
```

## Non-Windows

The setup uses a Windows directory **junction** and a **PowerShell** hook. On macOS/Linux: replace the
junction with a symlink (`ln -s "$PWD/commands" ~/.claude/commands`) and port `hooks/capture.ps1` to a
shell script (the logic is ~30 lines). The vault content itself is OS-agnostic markdown.

## Philosophy & credit

Distilled from real day-to-day use: markdown+git for control and auditability, Obsidian as the human
viewer, on-demand recall to keep token cost low and visible. Bring your own standards and lessons —
the shipped `standards/commit-messages.md` and `lessons/example-tool.md` are examples to delete.
