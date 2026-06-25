---
description: Refresh the recovery snapshot of global Claude Code config into the brain vault. Usage: /backup-config
---

Snapshot the global Claude Code config into the brain vault (`_meta/backups/`) for recovery. Run this
PowerShell, then report what changed (and commit to brain only if I say so):

```powershell
$bk = "<BRAIN_PATH>\_meta\backups"
New-Item -ItemType Directory -Force $bk | Out-Null
Copy-Item "$env:USERPROFILE\.claude\CLAUDE.md" "$bk\global-CLAUDE.md" -Force
$set = Get-Content "$env:USERPROFILE\.claude\settings.json" -Raw
$rx  = '(pylf_[A-Za-z0-9_]+|sk-[A-Za-z0-9_\-]+|AIza[A-Za-z0-9_\-]+|gh[oprs]_[A-Za-z0-9]+)'
$n   = ([regex]::Matches($set, $rx)).Count
[IO.File]::WriteAllText("$bk\global-settings.json", [regex]::Replace($set, $rx, '<REDACTED>'))

# ~/.claude.json — user-scope mcpServers (e.g. code-review-graph) + per-project MCP/trust state.
# Text-redact secrets + account identity (also sidesteps the JSON key-casing collision that breaks ConvertFrom-Json).
$cjPath = "$env:USERPROFILE\.claude.json"
$m = 0
if (Test-Path $cjPath) {
  $cj = Get-Content $cjPath -Raw
  $rxSecret = '(pylf_[A-Za-z0-9_]+|sk-[A-Za-z0-9_\-]+|AIza[A-Za-z0-9_\-]+|gh[oprs]_[A-Za-z0-9]+|(?i:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^"\s]+)'
  $rxKey    = '(?i)("(?:access_?token|refresh_?token|api[_-]?key|client[_-]?secret|password|passwd|secret|connectionString)"\s*:\s*")[^"]*(")'
  $rxId     = '(?i)("(?:emailAddress|accountUuid|organizationUuid|userID|machineID|organizationName|displayName)"\s*:\s*")[^"]*(")'
  $rxEmail  = '[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}'
  $m = ([regex]::Matches($cj,$rxSecret)).Count + ([regex]::Matches($cj,$rxKey)).Count + ([regex]::Matches($cj,$rxId)).Count + ([regex]::Matches($cj,$rxEmail)).Count
  $cj = [regex]::Replace($cj, $rxSecret, '<REDACTED>')
  $cj = [regex]::Replace($cj, $rxKey,   '${1}<REDACTED>${2}')
  $cj = [regex]::Replace($cj, $rxId,    '${1}<REDACTED>${2}')
  $cj = [regex]::Replace($cj, $rxEmail, '<REDACTED-EMAIL>')
  [IO.File]::WriteAllText("$bk\global-dotclaude.json", $cj)
}
"backed up global CLAUDE.md + settings.json (redacted $n) + ~/.claude.json (redacted $m) -> $bk"
```

The snapshot is secrets-redacted and feeds `_meta/backups/RESTORE.md`. Run it whenever you change your
global `~/.claude/CLAUDE.md`, `settings.json`, or `~/.claude.json` (e.g. after adding/removing a
user-scope MCP server like `code-review-graph`).
