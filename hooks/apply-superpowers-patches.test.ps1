#requires -Version 7
# Tests for apply-superpowers-patches.ps1 — the self-healing Superpowers patcher.
# Run: pwsh -NoProfile -File apply-superpowers-patches.test.ps1

$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'apply-superpowers-patches.ps1'
$fail = 0
function Check($name, $cond) {
  if ($cond) { Write-Host "  PASS $name" } else { Write-Host "  FAIL $name" -ForegroundColor Red; $script:fail++ }
}

# --- Build a throwaway fake plugins root mimicking the real layout ---
$root = Join-Path ([System.IO.Path]::GetTempPath()) ("sp-patch-test-" + [guid]::NewGuid().ToString('N'))
$verDir = Join-Path $root 'cache\claude-plugins-official\superpowers\9.9.9'
$skillDir = Join-Path $verDir 'skills\brainstorming'
New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
$skill = Join-Path $skillDir 'SKILL.md'
Set-Content -LiteralPath $skill -Value "# Brainstorming`n`nOriginal body.`n" -NoNewline

$installed = @{
  version = 2
  plugins = @{ 'superpowers@claude-plugins-official' = @(@{ scope='user'; installPath=$verDir; version='9.9.9' }) }
} | ConvertTo-Json -Depth 6
Set-Content -LiteralPath (Join-Path $root 'installed_plugins.json') -Value $installed

$patchDir = Join-Path $PSScriptRoot 'patches'
$marker = '<!-- BRAIN-PATCH:brainstorming-recommendation START -->'

try {
  # First run: should inject the marker exactly once.
  & pwsh -NoProfile -File $script -PluginsRoot $root -PatchDir $patchDir -Quiet | Out-Null
  $c1 = Get-Content -Raw -LiteralPath $skill
  $count1 = ([regex]::Matches($c1, [regex]::Escape($marker))).Count
  Check 'injects marker on first run' ($count1 -eq 1)
  Check 'preserves original body' ($c1.Contains('Original body.'))

  # Second run: idempotent — no duplicate injection.
  & pwsh -NoProfile -File $script -PluginsRoot $root -PatchDir $patchDir -Quiet | Out-Null
  $c2 = Get-Content -Raw -LiteralPath $skill
  $count2 = ([regex]::Matches($c2, [regex]::Escape($marker))).Count
  Check 'idempotent on second run' ($count2 -eq 1)

  # Simulate an update: new version dir, fresh unpatched SKILL.md, repointed manifest.
  $verDir2 = Join-Path $root 'cache\claude-plugins-official\superpowers\9.9.10'
  $skillDir2 = Join-Path $verDir2 'skills\brainstorming'
  New-Item -ItemType Directory -Force -Path $skillDir2 | Out-Null
  $skill2 = Join-Path $skillDir2 'SKILL.md'
  Set-Content -LiteralPath $skill2 -Value "# Brainstorming v2`n" -NoNewline
  $installed2 = @{
    version = 2
    plugins = @{ 'superpowers@claude-plugins-official' = @(@{ scope='user'; installPath=$verDir2; version='9.9.10' }) }
  } | ConvertTo-Json -Depth 6
  Set-Content -LiteralPath (Join-Path $root 'installed_plugins.json') -Value $installed2

  $stdout = & pwsh -NoProfile -File $script -PluginsRoot $root -PatchDir $patchDir
  $c3 = Get-Content -Raw -LiteralPath $skill2
  Check 're-applies to new version after update' ($c3.Contains($marker))
  Check 'emits SessionStart notice on (re)apply' ($stdout -and ($stdout -join '').Contains('hookSpecificOutput'))
}
finally {
  Remove-Item -Recurse -Force -LiteralPath $root -ErrorAction SilentlyContinue
}

if ($fail -gt 0) { Write-Host "FAILED: $fail" -ForegroundColor Red; exit 1 } else { Write-Host 'ALL PASS' -ForegroundColor Green; exit 0 }
