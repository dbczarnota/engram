#requires -Version 7
<#
  brain-starter guided installer.
  Walks install + config step by step: preview -> confirm [Y/n/skip] -> backup -> apply.
  Idempotent and re-runnable. Use -DryRun to preview without writing anything.

  Usage:  pwsh -NoProfile -File .\setup.ps1
          pwsh -NoProfile -File .\setup.ps1 -BrainPath "C:\path\to\brain"
          pwsh -NoProfile -File .\setup.ps1 -DryRun
#>
[CmdletBinding()]
param(
  [string]$BrainPath  = $PSScriptRoot,
  [string]$ConfigRoot = (Join-Path $env:USERPROFILE '.claude'),
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\setup.lib.ps1"

$BrainPath  = (Resolve-Path $BrainPath).Path.TrimEnd('\')
$script:backups = @()
$script:manual  = @()

function Confirm-Step {
  param([string]$Prompt)
  if ($DryRun) { Write-Host "  (dry-run: nothing applied)"; return $false }
  $ans = Read-Host "  $Prompt [Y/n/skip]"
  return ($ans -notmatch '^(n|no|s|skip)$')   # Enter / y => yes
}
function Backup-File {
  param([string]$Path)
  if (Test-Path $Path) {
    $bak = "$Path.bak.$(Get-Date -Format yyyyMMdd-HHmmss)"
    Copy-Item -LiteralPath $Path $bak -Force
    $script:backups += $bak
    Write-Host "  backup: $bak"
  }
}
function Read-Settings {
  param([string]$Path)
  if (Test-Path $Path) { return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable) }
  return @{}
}
function Write-Settings {
  param([string]$Path, $Obj)
  $dir = Split-Path $Path -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  ($Obj | ConvertTo-Json -Depth 32) | Set-Content -LiteralPath $Path -Encoding UTF8
}
function Step { param([string]$Title) Write-Host "`n$Title" }

Write-Host "brain-starter installer  (vault: $BrainPath)"
if ($DryRun) { Write-Host "DRY RUN - no files will be changed." }

# [1/8] Confirm vault path
Step "[1/9] Vault path"
Write-Host "  Using vault at: $BrainPath"
if (-not $DryRun -and -not (Confirm-Step "Is this correct?")) {
  Write-Error "Re-run with -BrainPath ""C:\path\to\brain"""; exit 1
}

# [2/9] Substitute <BRAIN_PATH>
Step "[2/9] Substitute <BRAIN_PATH> placeholder"
try {
  $hits = Get-ChildItem $BrainPath -Recurse -File -Include *.md, *.ps1, *.json |
    Where-Object { $_.Name -ne 'setup.ps1' -and $_.FullName -notmatch '\\\.venv\\' -and $_.FullName -notmatch '\\\.index\\' } |
    Where-Object { (Get-Content $_.FullName -Raw) -match '<BRAIN_PATH>' }
  if (-not $hits) { Write-Host "  already substituted (no <BRAIN_PATH> left) [ok]" }
  else {
    Write-Host "  Will replace <BRAIN_PATH> in $($hits.Count) file(s)."
    if (Confirm-Step "Substitute now?") {
      foreach ($f in $hits) {
        $c = Get-Content $f.FullName -Raw
        [IO.File]::WriteAllText($f.FullName, $c.Replace('<BRAIN_PATH>', $BrainPath))
      }
      Write-Host "  applied [ok]"
    } else { Write-Host "  skipped" }
  }
} catch { Write-Warning "  step failed: $_" }

# [3/8] Junction ~/.claude/commands
Step "[3/9] Install slash-commands (junction ~/.claude/commands)"
try {
  $link = Join-Path $ConfigRoot 'commands'
  $target = "$BrainPath\commands"
  switch (Get-JunctionState -Path $link -Target $target) {
    'ours'   { Write-Host "  already linked [ok]" }
    'absent' {
      Write-Host "  Will create junction: $link -> $target"
      if (Confirm-Step "Create it?") {
        New-Item -ItemType Directory -Force (Split-Path $link -Parent) | Out-Null
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        Write-Host "  created [ok]"
      } else { Write-Host "  skipped" }
    }
    default {
      Write-Host "  $link already exists (not ours). It will be backed up (renamed) then replaced."
      if (Confirm-Step "Back up and replace?") {
        $bak = "$link.bak.$(Get-Date -Format yyyyMMdd-HHmmss)"
        Move-Item -LiteralPath $link $bak; $script:backups += $bak
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        Write-Host "  backup: $bak; created [ok]"
      } else { Write-Host "  skipped - copy '$target\*.md' into '$link' manually if you prefer" }
    }
  }
} catch { Write-Warning "  step failed: $_" }

# [4/9] Install bundled skills (~/.claude/skills) — copy, not junction
Step "[4/9] Install bundled skills (copy into ~/.claude/skills)"
# Copy (seed), not junction: skills are installed into ~/.claude/skills as standalone copies so a tool
# that refreshes its own skill there never pushes writes back into this repo.
try {
  $skillsSrc = Join-Path $BrainPath 'skills'
  if (-not (Test-Path $skillsSrc)) { Write-Host "  no bundled skills to install [ok]" }
  else {
    $skillsDst = Join-Path $ConfigRoot 'skills'
    foreach ($sk in Get-ChildItem $skillsSrc -Directory) {
      $dst = Join-Path $skillsDst $sk.Name
      if (Test-Path $dst) {
        Write-Host "  '$($sk.Name)' already installed at $dst"
        if (Confirm-Step "Overwrite '$($sk.Name)' (a backup is kept)?") {
          $bak = "$dst.bak.$(Get-Date -Format yyyyMMdd-HHmmss)"
          Move-Item -LiteralPath $dst $bak; $script:backups += $bak
          Copy-Item -LiteralPath $sk.FullName -Destination $dst -Recurse
          Write-Host "  backup: $bak; copied [ok]"
        } else { Write-Host "  skipped '$($sk.Name)'" }
      } else {
        Write-Host "  Will install skill '$($sk.Name)' -> $dst"
        if (Confirm-Step "Install '$($sk.Name)'?") {
          New-Item -ItemType Directory -Force $skillsDst | Out-Null
          Copy-Item -LiteralPath $sk.FullName -Destination $dst -Recurse
          Write-Host "  copied [ok]"
        } else { Write-Host "  skipped '$($sk.Name)'" }
      }
    }
    $script:manual += "youtube-transcribe skill: put STREAM2LLM_API_KEY=str_... in ~/.claude/stream2llm.env (see the skill's stream2llm.env.example)."
  }
} catch { Write-Warning "  step failed: $_" }

# [5/9] Register the memory-loop hooks in settings.json
Step "[5/9] Register hooks in settings.json (memory loop + auto-recall)"
# The harness the vault actually runs wires FIVE events — not just SessionEnd. SessionEnd never fires
# in the VS Code extension (the backend is hard-killed, not gracefully exited), so `Stop` drives the
# capture there (upsert one journal block per session); `PostToolUse` tracks edited files and strips
# the auto block on /checkpoint; `SessionStart` reminds about lesson drafts and prunes stale scratch.
# Registering only SessionEnd would leave a VS Code user with no auto-journal at all.
try {
  $settingsPath = Join-Path $ConfigRoot 'settings.json'
  $hookSpecs = @(
    @{ Event = 'Stop';             Script = 'stop.ps1';              Matcher = $null },
    @{ Event = 'SessionEnd';       Script = 'capture.ps1';           Matcher = $null },
    @{ Event = 'SessionStart';     Script = 'sessionstart.ps1';      Matcher = $null },
    @{ Event = 'PostToolUse';      Script = 'posttooluse-track.ps1'; Matcher = 'Edit|Write|MultiEdit' },
    @{ Event = 'UserPromptSubmit'; Script = 'autorecall.ps1';        Matcher = $null }
  )
  $backedUp = $false
  foreach ($spec in $hookSpecs) {
    $settings = Read-Settings $settingsPath
    $cmd = "pwsh -NoProfile -File ""$BrainPath\hooks\$($spec.Script)"""
    $res = if ($spec.Matcher) { Merge-Hook -Settings $settings -EventName $spec.Event -Command $cmd -Matcher $spec.Matcher }
           else               { Merge-Hook -Settings $settings -EventName $spec.Event -Command $cmd }
    if (-not $res.Changed) { Write-Host "  $($spec.Event) -> $($spec.Script) already configured [ok]"; continue }
    Write-Host "  Will add $($spec.Event) hook:`n    $cmd"
    if (Confirm-Step "Add $($spec.Event) hook to settings.json?") {
      if (-not $backedUp) { Backup-File $settingsPath; $backedUp = $true }
      Write-Settings $settingsPath $res.Settings; Write-Host "  applied [ok]"
    } else { Write-Host "  skipped" }
  }
} catch { Write-Warning "  step failed: $_" }

# [6/9] autoMemoryEnabled:false
Step "[6/9] Disable competing auto-memory in settings.json"
try {
  $settingsPath = Join-Path $ConfigRoot 'settings.json'
  $settings = Read-Settings $settingsPath
  $res = Set-AutoMemoryDisabled -Settings $settings
  if (-not $res.Changed) { Write-Host "  autoMemoryEnabled already false [ok]" }
  else {
    Write-Host "  Will set: autoMemoryEnabled -> false"
    if (Confirm-Step "Apply?") {
      Backup-File $settingsPath; Write-Settings $settingsPath $res.Settings; Write-Host "  applied [ok]"
    } else { Write-Host "  skipped" }
  }
  $script:manual += "Disable any claude-mem-style PLUGIN manually (a script can't toggle plugins)."
} catch { Write-Warning "  step failed: $_" }

# [7/9] CLAUDE.md vault pointer
Step "[7/9] Add vault pointer to ~/.claude/CLAUDE.md"
try {
  $claudeMd = Join-Path $ConfigRoot 'CLAUDE.md'
  $pointerTemplate = @'
## Knowledge Vault
A knowledge vault lives at `{0}` (git repo + Obsidian vault); single source of truth for standards, lessons, project state, research.
- Before designing/building, consult `brain/standards/` and `brain/lessons/` - grep, don't load wholesale. Use /recall.
- When I reference another project, grep `brain/projects/`.
- Create standards/lessons ONLY when I explicitly say so (/remember-standard, /remember-lesson).
- Consult the vault before answering when I reference past decisions, "how we did X", or another project - you don't need me to type /recall.
'@
  $block = $pointerTemplate -f $BrainPath
  $current = if (Test-Path $claudeMd) { Get-Content -LiteralPath $claudeMd -Raw } else { '' }
  $res = Update-ClaudePointer -Text $current -Block $block
  if (-not $res.Changed) { Write-Host "  pointer already present and current [ok]" }
  else {
    Write-Host "  Will insert/refresh the brain-vault-pointer block."
    if (Confirm-Step "Apply?") {
      Backup-File $claudeMd
      $dir = Split-Path $claudeMd -Parent
      if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
      Set-Content -LiteralPath $claudeMd -Value $res.Text -Encoding UTF8
      Write-Host "  applied [ok]"
    } else { Write-Host "  skipped" }
  }
} catch { Write-Warning "  step failed: $_" }

# [8/9] Optional AI add-ons: CRG code graph (no key) + semantic search (needs a Gemini key)
Step "[8/9] Optional AI add-ons (CRG code graph + semantic search)"
$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
if ($DryRun) { Write-Host "  (dry-run: skipping optional add-ons)" }
elseif (-not $hasUv) { Write-Host "  skipped (uv not found)" }
else {
  $sem = "$BrainPath\_meta\semantic"
  # 7a CRG (code-review-graph) — per-repo code graph served over MCP. No API key needed: build +
  # the commit hook use tree-sitter AST + a local embedder. The MCP server registers user-scope.
  if (Confirm-Step "Install CRG (code-review-graph, code knowledge graph over MCP, no API key needed)?") {
    & uv tool install code-review-graph
    $script:manual += "CRG: run /onboard-project on a repo to build its code graph + install the auto-rebuild hook (code-only, no API key)."
    Write-Host "  CRG installed [ok]"
  }
  # 7b Semantic search — needs a Gemini API key (it embeds the markdown vault).
  if (Test-Path "$sem\pyproject.toml") {
    if (Confirm-Step "Enable semantic search (needs a Gemini API key)?") {
      $key = Read-Host "  Paste your Gemini API key (blank to skip)"
      if ($key) {
        & uv sync --directory $sem | Out-Null
        Set-Content -LiteralPath "$sem\.env" -Value "GEMINI_API_KEY=$key" -Encoding UTF8
        & uv run --directory $sem --env-file "$sem\.env" python -m reindex
        Write-Host "  semantic search ready [ok]"
      } else { Write-Host "  semantic skipped (no key)" }
    }
  } else { Write-Host "  semantic skipped (_meta/semantic missing)" }
}

# [9/9] Guided manual steps
Step "[9/9] Manual steps (these can't be automated)"
$script:manual += "Install the 'superpowers' plugin (Engram is built around its brainstorm->spec->plan workflow): in Claude Code run  /plugin marketplace add anthropics/claude-plugins-official  then  /plugin install superpowers@claude-plugins-official"
$script:manual += "Open this folder in Obsidian and enable the Dataview community plugin."
$script:manual += "Restart Claude Code, then run '/recall test' to confirm the commands load."

Write-Host "`n=== SUMMARY ==="
Write-Host "Remaining manual steps:"
$script:manual | ForEach-Object { Write-Host "  - $_" }
if ($script:backups.Count) {
  Write-Host "Backups created:"
  $script:backups | ForEach-Object { Write-Host "  - $_" }
}
Write-Host "`nDone."
