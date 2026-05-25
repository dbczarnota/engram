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
Step "[1/8] Vault path"
Write-Host "  Using vault at: $BrainPath"
if (-not $DryRun -and -not (Confirm-Step "Is this correct?")) {
  Write-Error "Re-run with -BrainPath ""C:\path\to\brain"""; exit 1
}

# [2/8] Substitute <BRAIN_PATH>
Step "[2/8] Substitute <BRAIN_PATH> placeholder"
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
Step "[3/8] Install slash-commands (junction ~/.claude/commands)"
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

# [4/8] SessionEnd capture hook
Step "[4/8] Register SessionEnd capture hook in settings.json"
try {
  $settingsPath = Join-Path $ConfigRoot 'settings.json'
  $hookCmd = "pwsh -NoProfile -File ""$BrainPath\hooks\capture.ps1"""
  $settings = Read-Settings $settingsPath
  $res = Merge-SessionEndHook -Settings $settings -Command $hookCmd
  if (-not $res.Changed) { Write-Host "  hook already configured [ok]" }
  else {
    Write-Host "  Will add hook command:`n    $hookCmd"
    if (Confirm-Step "Add to settings.json?") {
      Backup-File $settingsPath; Write-Settings $settingsPath $res.Settings; Write-Host "  applied [ok]"
    } else { Write-Host "  skipped" }
  }
} catch { Write-Warning "  step failed: $_" }

# [5/8] autoMemoryEnabled:false
Step "[5/8] Disable competing auto-memory in settings.json"
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

# [6/8] CLAUDE.md vault pointer
Step "[6/8] Add vault pointer to ~/.claude/CLAUDE.md"
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

# [7/8] Optional AI add-ons (semantic + Graphify), shared Gemini key
Step "[7/8] Optional AI add-ons (semantic search + Graphify)"
$hasUv = [bool](Get-Command uv -ErrorAction SilentlyContinue)
if ($DryRun) { Write-Host "  (dry-run: skipping optional add-ons)" }
elseif (-not (Confirm-Step "Set up AI add-ons now (needs a Gemini API key)?")) { Write-Host "  skipped" }
else {
  $key = Read-Host "  Paste your Gemini API key (blank to skip)"
  if (-not $key) { Write-Host "  no key - skipping add-ons" }
  else {
    $sem = "$BrainPath\_meta\semantic"
    # 7a semantic
    if ($hasUv -and (Test-Path "$sem\pyproject.toml")) {
      if (Confirm-Step "Enable semantic search (uv sync + reindex)?") {
        & uv sync --project $sem | Out-Null
        Set-Content -LiteralPath "$sem\.env" -Value "GEMINI_API_KEY=$key" -Encoding UTF8
        & uv run --project $sem --env-file "$sem\.env" python -m reindex
        Write-Host "  semantic search ready [ok]"
      }
    } else { Write-Host "  semantic skipped (uv not found or _meta/semantic missing)" }
    # 7b Graphify
    if ($hasUv) {
      if (Confirm-Step "Install Graphify (codebase knowledge graph)?") {
        & uv tool install graphifyy --with openai
        & graphify install --platform windows
        $script:manual += "Graphify: set GEMINI_API_KEY in your environment, then run 'graphify .' inside a repo."
        Write-Host "  Graphify installed [ok]"
      }
    } else { Write-Host "  Graphify skipped (uv not found)" }
  }
}

# [8/8] Guided manual steps
Step "[8/8] Manual steps (these can't be automated)"
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
