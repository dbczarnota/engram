#requires -Version 7
# SessionEnd hook: append an LLM session summary to the active project's journal.
# Reads hook JSON from stdin: { cwd, transcript_path, session_id, ... }.
# Best-effort: any failure exits 0 so it never blocks session end.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\capture.lib.ps1"
try {
  # Recursion guard: capture summarization can spawn a sub-session (e.g. the claude-cli backend),
  # whose own SessionEnd would re-invoke this hook. If we're already inside a capture, no-op.
  # (BRAIN_CAPTURE_ACTIVE is set by Invoke-Capture before it calls the summarizer.)
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json

  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }

  # Heartbeat: unconditional proof the hook fired.
  try {
    $hb = "$brain\hooks\hook-fired.log"
    Add-Content -Path $hb -Value ("{0}  fired  reason={1}  cwd={2}" -f (Get-Date -Format s), $hook.reason, $hook.cwd)
  } catch {}

  $sid = "" + $hook.session_id
  if (-not $sid) { exit 0 }
  $slug = Resolve-Slug -Brain $brain -Cwd ("" + $hook.cwd)
  if (-not $slug) { exit 0 }

  $logf = "$brain\hooks\capture.log"
  $log = { param($m) try { Add-Content -Path $logf -Value ("{0}  {1}" -f (Get-Date -Format s), $m) } catch {} }

  if (-not (Test-ShouldSummarize -Brain $brain -SessionId $sid)) { & $log "skip (gate): $slug $sid"; exit 0 }
  $wrote = Invoke-Capture -Brain $brain -Slug $slug -SessionId $sid -TranscriptPath ("" + $hook.transcript_path) -Cwd ("" + $hook.cwd)
  if ($wrote) {
    Set-ScratchFlag -Brain $brain -SessionId $sid -Name "summarized" -Value $true
    & $log "captured: $slug ($sid)"
  } else { & $log "bail: no entry written ($slug $sid)"; exit 0 }

  try { Invoke-Reindex -Brain $brain -SessionId $sid } catch {}
  exit 0
} catch {
  exit 0   # never block session end
}
