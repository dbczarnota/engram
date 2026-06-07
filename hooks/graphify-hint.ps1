#requires -Version 7
# UserPromptSubmit hook: nudge the agent to use the repo's graphify code graph for structural/impact
# questions (it is otherwise never consulted). Best-effort: any failure exits 0 with no output.
$ErrorActionPreference = "Stop"
try {
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json
  $prompt = "" + $hook.prompt
  $cwd = "" + $hook.cwd
  $sid = "" + $hook.session_id
  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }

  # Toggle.
  $cfgPath = "$brain\_meta\engram.json"
  if (Test-Path $cfgPath) {
    try {
      $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
      if ($cfg.graphify -and $cfg.graphify.hint -and $cfg.graphify.hint.enabled -eq $false) { exit 0 }
    } catch {}
  }

  # Structural-intent gate (EN + PL).
  $rx = 'depends on|what calls|where .* used|blast.?radius|call graph|imports|architecture|coupl|co zależy|gdzie .* używan|co wywołuje|zależnoś|architektur|powiązan'
  if ($prompt -notmatch "(?i)$rx") { exit 0 }

  # Graph must exist and the CLI must be available.
  $gout = Join-Path $cwd "graphify-out"
  if (-not (Test-Path $gout)) { exit 0 }
  if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) { exit 0 }

  # Once-per-session dedup via the memory-loop scratch.
  if (-not $sid) { exit 0 }
  . "$PSScriptRoot\capture.lib.ps1"
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if ($s.gfxHinted) { exit 0 }

  # Light freshness check: GRAPH_REPORT's commit vs HEAD.
  $stale = ""
  try {
    $report = Join-Path $gout "GRAPH_REPORT.md"
    if (Test-Path $report) {
      $m = [regex]::Match((Get-Content $report -Raw), 'Built from commit:\s*`?([0-9a-fA-F]{7,40})`?')
      if ($m.Success) {
        $head = (& git -C $cwd rev-parse HEAD 2>$null) -join ""
        if ($head -and -not $head.StartsWith($m.Groups[1].Value)) { $stale = " (graph stale — run ``graphify update .``)" }
      }
    }
  } catch {}

  Set-ScratchFlag -Brain $brain -SessionId $sid -Name "gfxHinted" -Value $true
  $msg = "🕸 Code graph available for this repo — for structure/impact questions prefer ``graphify query ""<your question>""`` (or ``path A B`` / ``explain Node``) instead of grep alone.$stale"
  $out = @{ hookSpecificOutput = @{ hookEventName = "UserPromptSubmit"; additionalContext = $msg } }
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  $out | ConvertTo-Json -Depth 6 -Compress
  exit 0
} catch { exit 0 }
