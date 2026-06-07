#requires -Version 7
# UserPromptSubmit hook: inject a small "possibly relevant vault notes" hint.
# Best-effort: any failure exits 0 with no output so it never blocks a turn.
$ErrorActionPreference = "Stop"
try {
  # Don't fire during the SessionEnd capture's headless `claude -p` sub-session.
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }

  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json
  $prompt = "" + $hook.prompt
  $sid = "" + $hook.session_id

  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }
  $sem = "$brain\_meta\semantic"

  try { . "$PSScriptRoot\capture.lib.ps1"; Add-ScratchPrompt -Brain $brain -SessionId $sid -Prompt $prompt } catch {}

  # Honor the toggle before spawning anything.
  $cfgPath = "$brain\_meta\engram.json"
  if (Test-Path $cfgPath) {
    try {
      $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
      if ($cfg.autoRecall -and $cfg.autoRecall.enabled -eq $false) { exit 0 }
    } catch {}
  }

  # Cheap pre-gate: skip obvious trivia without spawning Python.
  if (($prompt -split '\s+' | Where-Object { $_ }).Count -lt 4) { exit 0 }

  $envFile = "$sem\.env"
  $runArgs = @('run', '--directory', $sem)
  if (Test-Path $envFile) { $runArgs += @('--env-file', $envFile) }
  $runArgs += @('python', '-m', 'autorecall', $prompt, $sid)

  $prev = [Console]::OutputEncoding
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  try { $hint = (& uv @runArgs 2>$null) -join "`n" } finally { [Console]::OutputEncoding = $prev }
  $hint = $hint.Trim()
  if (-not $hint) { exit 0 }
  if ($hint.Length -gt 9000) { $hint = $hint.Substring(0, 9000) }  # stay under the 10k cap

  $out = @{ hookSpecificOutput = @{ hookEventName = "UserPromptSubmit"; additionalContext = $hint } }
  $out | ConvertTo-Json -Depth 6 -Compress
  exit 0
} catch { exit 0 }
