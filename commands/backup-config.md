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
"backed up global CLAUDE.md + settings.json (redacted $n secret-like value(s)) -> $bk"
```

The snapshot is secrets-redacted and feeds `_meta/backups/RESTORE.md`. Run it whenever you change your
global `~/.claude/CLAUDE.md` or `settings.json`.
