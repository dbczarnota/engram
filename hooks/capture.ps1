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

  # Auto-reindex the semantic index so it tracks the vault (the journal entry just written, plus any
  # edits this session made, land before the next auto-recall). Best-effort; honors the semantic
  # toggle and no-ops if the index module or uv isn't present. Content-hash cache keeps it cheap.
  try {
    $sem = "$brain\_meta\semantic"
    $semOn = $true
    if (Test-Path "$brain\_meta\engram.json") {
      $cfg = Get-Content "$brain\_meta\engram.json" -Raw | ConvertFrom-Json
      if ($cfg.semantic -and $cfg.semantic.enabled -eq $false) { $semOn = $false }
    }
    if ($semOn -and (Test-Path "$sem\reindex.py") -and (Get-Command uv -ErrorAction SilentlyContinue)) {
      $runArgs = @('run', '--directory', $sem)
      if (Test-Path "$sem\.env") { $runArgs += @('--env-file', "$sem\.env") }
      $runArgs += @('python', '-m', 'reindex')
      $r = (& uv @runArgs 2>$null) -join "`n"
      & $log ("reindex: $r")
    }
  } catch { & $log "reindex error: $($_.Exception.Message)" }
  exit 0
} catch {
  exit 0   # never block session end
}
