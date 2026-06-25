#requires -Version 7
# Stop hook: cheap per-turn accumulation (no LLM). On a long-session threshold OR a fresh commit,
# write a (partial) journal entry via the shared summarizer, then reset the turn counter.
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

  Add-ScratchTurn -Brain $brain -SessionId $sid -Prompt ""

  # Detect a new commit since last check (best-effort; flags the scratch for commit-trigger).
  $cwd = "" + $hook.cwd
  try {
    $head = (& git -C $cwd rev-parse HEAD 2>$null) -join ""
    $s = Get-SessionScratch -Brain $brain -SessionId $sid
    if ($head -and $head -ne ("" + $s.lastHead)) {
      if ($s.lastHead) { Set-ScratchFlag -Brain $brain -SessionId $sid -Name "committed" -Value $true }
      Set-ScratchFlag -Brain $brain -SessionId $sid -Name "lastHead" -Value $head
    }
  } catch {}

  $first   = if ($env:BRAIN_FIRST_THRESHOLD)   { [int]$env:BRAIN_FIRST_THRESHOLD }   else { 8 }
  $refresh = if ($env:BRAIN_REFRESH_THRESHOLD) { [int]$env:BRAIN_REFRESH_THRESHOLD } else { 25 }
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  $turnThreshold = if ($s.everSummarized) { $refresh } else { $first }
  $hitThreshold = ([int]$s.turns -ge $turnThreshold)

  # Commit-trigger requires a small minimum of turns to avoid noise.
  $commitTrigger = ($s.committed -and [int]$s.turns -ge 4)

  if (($hitThreshold -or $commitTrigger) -and -not $env:BRAIN_NO_SUMMARIZE) {
    $slug = Resolve-Slug -Brain $brain -Cwd $cwd
    if ($slug -and (Test-ShouldSummarize -Brain $brain -SessionId $sid)) {
      $wrote = Invoke-Capture -Brain $brain -Slug $slug -SessionId $sid -TranscriptPath ("" + $hook.transcript_path) -Cwd $cwd
      if ($wrote) {
        Set-ScratchFlag -Brain $brain -SessionId $sid -Name "everSummarized" -Value $true
        Set-ScratchFlag -Brain $brain -SessionId $sid -Name "turns" -Value 0
        Set-ScratchFlag -Brain $brain -SessionId $sid -Name "committed" -Value $false
        Invoke-Reindex -Brain $brain -SessionId $sid -ThrottleMinutes 10
      }
    }
  }
  exit 0
} catch { exit 0 }
