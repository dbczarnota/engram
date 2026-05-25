#requires -Version 7
# SessionEnd hook: append an LLM session summary to the active project's journal.
# Reads hook JSON from stdin: { cwd, transcript_path, session_id, ... }.
# Best-effort: any failure exits 0 so it never blocks session end.
$ErrorActionPreference = "Stop"
try {
  # Recursion guard: the `claude -p` call below spawns a sub-session whose own SessionEnd
  # re-invokes this hook. If we're already inside a capture, no-op immediately.
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json

  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "C:\Users\czarn\Documents\A_PYTHON\brain" }

  # Heartbeat: unconditional proof the hook fired (debug whether the host fires SessionEnd at all).
  try {
    $hb = "$brain\hooks\hook-fired.log"
    New-Item -ItemType Directory -Force (Split-Path $hb) | Out-Null
    Add-Content -Path $hb -Value ("{0}  fired  reason={1}  cwd={2}" -f (Get-Date -Format s), $hook.reason, $hook.cwd)
  } catch {}

  $mapPath = "$brain\_meta\project-map.json"
  if (-not (Test-Path $mapPath)) { exit 0 }
  $map = Get-Content $mapPath -Raw | ConvertFrom-Json

  # Resolve cwd -> slug (longest matching path prefix wins)
  $cwd = ("" + $hook.cwd).TrimEnd('\')
  $slug = $null; $best = -1
  foreach ($p in $map.PSObject.Properties) {
    $key = $p.Name.TrimEnd('\')
    if ($cwd -eq $key -or $cwd.StartsWith("$key\")) {
      if ($key.Length -gt $best) { $best = $key.Length; $slug = $p.Value }
    }
  }
  if (-not $slug) { exit 0 }   # unknown project -> no-op

  $journal = "$brain\projects\$slug\journal.md"
  if (-not (Test-Path $journal)) { exit 0 }

  # Condense the transcript and summarize via headless claude.
  if (-not $hook.transcript_path -or -not (Test-Path $hook.transcript_path)) { exit 0 }
  $lines = Get-Content $hook.transcript_path -Tail 400
  $prompt = @"
Summarize this Claude Code session for a project journal. Output 5-10 terse bullets:
decisions made, what changed, what's in progress, blockers. No preamble. If nothing
substantive happened, output exactly: SKIP
"@
  $env:BRAIN_CAPTURE_ACTIVE = "1"   # mark so the nested session's SessionEnd hook no-ops (see guard above)
  $summary = ($lines -join "`n") | claude -p $prompt 2>$null
  if (-not $summary -or $summary.Trim() -eq "SKIP") { exit 0 }

  $date = Get-Date -Format "yyyy-MM-dd HH:mm"
  $entry = "## $date - session $($hook.session_id)`n$summary`n`n"
  $existing = if (Test-Path $journal) { Get-Content $journal -Raw } else { "" }
  Set-Content -Path $journal -Value ($entry + $existing) -Encoding utf8
  exit 0
} catch {
  exit 0   # never block session end
}
