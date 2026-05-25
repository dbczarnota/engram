#requires -Version 7
<#
  brain-starter setup.
  Substitutes the <BRAIN_PATH> placeholder with this vault's absolute path, then installs the
  slash-commands globally via a junction. Prints the remaining manual steps.

  Usage:  pwsh -NoProfile -File .\setup.ps1            # uses this folder as the vault
          pwsh -NoProfile -File .\setup.ps1 -BrainPath "C:\path\to\brain"
#>
param([string]$BrainPath = $PSScriptRoot)
$ErrorActionPreference = "Stop"

$BrainPath = (Resolve-Path $BrainPath).Path.TrimEnd('\')
Write-Host "Configuring brain vault at: $BrainPath`n"

# 1) Substitute the <BRAIN_PATH> placeholder everywhere (except this script).
$n = 0
Get-ChildItem $BrainPath -Recurse -File -Include *.md, *.ps1, *.json |
  Where-Object { $_.Name -ne 'setup.ps1' } |
  ForEach-Object {
    $c = Get-Content $_.FullName -Raw
    if ($c -match '<BRAIN_PATH>') {
      [IO.File]::WriteAllText($_.FullName, $c.Replace('<BRAIN_PATH>', $BrainPath))
      $n++
    }
  }
Write-Host "[1/2] Replaced <BRAIN_PATH> in $n file(s)."

# 2) Install slash-commands globally via a junction (Windows). mac/linux: use a symlink instead.
$link = "$env:USERPROFILE\.claude\commands"
$target = "$BrainPath\commands"
if (Test-Path $link) {
  Write-Host "[2/2] $link already exists - left untouched."
  Write-Host "      To use these commands, either copy '$target\*.md' into it, or remove it and re-run."
}
else {
  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  Write-Host "[2/2] Created junction: $link -> $target"
}

Write-Host "`n--- MANUAL STEPS (in Claude Code / settings) ---"
Write-Host "1. Register the session-end capture hook in ~/.claude/settings.json under `"hooks`":"
Write-Host "     SessionEnd -> command: pwsh -NoProfile -File `"$BrainPath\hooks\capture.ps1`""
Write-Host "2. Disable competing memory (recommended): set `"autoMemoryEnabled`": false in"
Write-Host "   ~/.claude/settings.json, and disable any claude-mem-style plugin."
Write-Host "3. Add the ~15-line vault pointer to your global ~/.claude/CLAUDE.md (see README.md)."
Write-Host "4. Open this folder in Obsidian and enable the Dataview community plugin."
Write-Host "5. Restart Claude Code, then run '/recall test' to verify the commands load."
