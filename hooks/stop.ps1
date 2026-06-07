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

  $threshold = if ($env:BRAIN_STOP_THRESHOLD) { [int]$env:BRAIN_STOP_THRESHOLD } else { 60 }
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  $hitThreshold = ([int]$s.turns -ge $threshold)
  if ($hitThreshold) { Set-ScratchFlag -Brain $brain -SessionId $sid -Name "thresholdHit" -Value $true }

  # Commit-trigger requires a small minimum of turns since start to avoid noise.
  $commitTrigger = ($s.committed -and [int]$s.turns -ge 4 -and -not $s.summarized)

  if (($hitThreshold -or $commitTrigger) -and -not $env:BRAIN_NO_SUMMARIZE) {
    $slug = Resolve-Slug -Brain $brain -Cwd $cwd
    if ($slug -and (Test-ShouldSummarize -Brain $brain -SessionId $sid)) {
      $wrote = Invoke-Capture -Brain $brain -Slug $slug -SessionId $sid -TranscriptPath ("" + $hook.transcript_path) -Cwd $cwd -Partial
      if ($wrote) {
        # Intentionally NOT setting summarized=true — partial entries may repeat across a long
        # session; only the SessionEnd capture finalizes (sets summarized) to block duplicate fires.
        Set-ScratchFlag -Brain $brain -SessionId $sid -Name "turns" -Value 0
        Set-ScratchFlag -Brain $brain -SessionId $sid -Name "committed" -Value $false
        Set-ScratchFlag -Brain $brain -SessionId $sid -Name "thresholdHit" -Value $false
      }
    }
  }
  exit 0
} catch { exit 0 }
