#requires -Version 7
# PreToolUse hook (matcher: Grep|Glob): when the repo has a code graph, remind the agent at the
# moment it reaches for raw search — the upstream `graphify claude install` pattern, in PowerShell
# (the upstream payload is sh-only and no-ops on Windows). Replaces the old UserPromptSubmit regex
# gate, which fired ~never (2 times in 30 days) and converted 0 times.
# Best-effort: any failure exits 0 with no output.
$ErrorActionPreference = "Stop"
try {
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json
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

  # Graph must exist and the CLI must be available.
  $gout = Join-Path $cwd "graphify-out"
  if (-not (Test-Path (Join-Path $gout "graph.json"))) { exit 0 }
  if (-not (Get-Command graphify -ErrorAction SilentlyContinue)) { exit 0 }

  # Cooldown: at most one hint per 5 minutes per session — repeats across a long session
  # (unlike the old once-per-session flag) without spamming every search in a burst.
  if (-not $sid) { exit 0 }
  . "$PSScriptRoot\capture.lib.ps1"
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  if ($s.gfxHintedAt -and (($now - [long]$s.gfxHintedAt) -lt 300)) { exit 0 }

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

  Set-ScratchFlag -Brain $brain -SessionId $sid -Name "gfxHintedAt" -Value $now
  $msg = "🕸 Code graph available for this repo — for structure/impact questions prefer ``graphify query ""<question>""`` (or ``path A B`` / ``explain Node`` / ``affected Node``) over raw search; it returns a scoped subgraph.$stale"
  $out = @{ hookSpecificOutput = @{ hookEventName = "PreToolUse"; additionalContext = $msg } }
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  $out | ConvertTo-Json -Depth 6 -Compress
  exit 0
} catch { exit 0 }
