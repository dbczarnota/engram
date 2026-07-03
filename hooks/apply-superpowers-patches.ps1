#requires -Version 7
<#
.SYNOPSIS
  Self-healing patcher for Superpowers plugin skills.

  Superpowers auto-updates in the background: Claude Code materializes a new version
  directory (cache/.../superpowers/<new>) and repoints installed_plugins.json, silently
  abandoning any local edits to the old version dir. This hook re-applies our own
  additions to whatever version is currently active.

  Runs at SessionStart. For each declared patch: locate the active target file, and if
  our marker is absent, append the canonical patch block. Idempotent (marker-gated).
  When it has to (re)apply — i.e. after a silent update — it surfaces a SessionStart
  notice so the update is visible instead of silent.

  Never throws in a way that breaks the session: all work is wrapped, exit is always 0.
#>
param(
  # Root that contains installed_plugins.json. Override for tests.
  [string]$PluginsRoot = (Join-Path $env:USERPROFILE ".claude\plugins"),
  # Dir holding canonical patch blocks. Override for tests.
  [string]$PatchDir = (Join-Path $PSScriptRoot "patches"),
  # Emit the SessionStart JSON notice. Off for tests (they assert on files, not stdout).
  [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

# ---- Declared patches: which canonical block goes into which plugin-relative file ----
# Keyed by plugin name (as it appears in installed_plugins.json, without @marketplace).
$Patches = @(
  @{
    Plugin   = 'superpowers'
    RelPath  = 'skills\brainstorming\SKILL.md'
    PatchFile = 'brainstorming-recommendation.md'
    Marker   = '<!-- BRAIN-PATCH:brainstorming-recommendation START -->'
  }
)

function Get-ActiveInstallPaths {
  param([string]$InstalledJsonPath, [string]$PluginName)
  if (-not (Test-Path $InstalledJsonPath)) { return @() }
  $data = Get-Content -Raw -LiteralPath $InstalledJsonPath | ConvertFrom-Json
  $paths = @()
  foreach ($prop in $data.plugins.PSObject.Properties) {
    # key looks like "superpowers@claude-plugins-official"
    if (($prop.Name -split '@')[0] -ne $PluginName) { continue }
    foreach ($entry in $prop.Value) {
      if ($entry.installPath) { $paths += $entry.installPath }
    }
  }
  return $paths
}

$applied = @()  # human-readable notes for the SessionStart message
$installedJson = Join-Path $PluginsRoot 'installed_plugins.json'

foreach ($p in $Patches) {
  try {
    $patchPath = Join-Path $PatchDir $p.PatchFile
    if (-not (Test-Path $patchPath)) { continue }
    $block = Get-Content -Raw -LiteralPath $patchPath

    $installPaths = Get-ActiveInstallPaths -InstalledJsonPath $installedJson -PluginName $p.Plugin
    foreach ($ip in $installPaths) {
      $target = Join-Path $ip $p.RelPath
      if (-not (Test-Path $target)) { continue }
      $content = Get-Content -Raw -LiteralPath $target
      if ($content.Contains($p.Marker)) { continue }  # already patched, nothing to do

      $sep = if ($content.EndsWith("`n")) { "`n" } else { "`n`n" }
      [System.IO.File]::WriteAllText($target, $content + $sep + $block, [System.Text.UTF8Encoding]::new($false))
      $ver = Split-Path (Split-Path (Split-Path (Split-Path $target -Parent) -Parent) -Parent) -Leaf
      $applied += "$($p.Plugin) $ver -> $($p.RelPath)"
    }
  } catch {
    # Never let a patch failure break the session; note it and move on.
    $applied += "ERROR patching $($p.Plugin)/$($p.RelPath): $($_.Exception.Message)"
  }
}

if (-not $Quiet -and $applied.Count -gt 0) {
  $msg = "Re-applied Superpowers patch(es) after a plugin update:`n- " + ($applied -join "`n- ")
  $out = @{ hookSpecificOutput = @{ hookEventName = "SessionStart"; additionalContext = $msg } }
  $out | ConvertTo-Json -Depth 6 -Compress
}

exit 0
