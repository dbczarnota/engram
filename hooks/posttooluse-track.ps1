#requires -Version 7
# PostToolUse hook (Edit|Write): append the touched file to the session scratch. No LLM, best-effort.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\capture.lib.ps1"
try {
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json
  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }
  $sid = "" + $hook.session_id
  if (-not $sid) { exit 0 }
  $fp = "" + $hook.tool_input.file_path
  if ($fp) { Add-ScratchFile -Brain $brain -SessionId $sid -File $fp }
  exit 0
} catch { exit 0 }
