#requires -Version 7
# SessionEnd hook: append an LLM session summary to the active project's journal.
# Reads hook JSON from stdin: { cwd, transcript_path, session_id, ... }.
# Best-effort: any failure exits 0 so it never blocks session end.
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\capture.lib.ps1"
try {
  # Recursion guard: the `claude -p` call below spawns a sub-session whose own SessionEnd
  # re-invokes this hook. If we're already inside a capture, no-op immediately.
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json

  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }

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

  # Diagnostic log: record each decision point so a real session end is observable.
  $logf = "$brain\hooks\capture.log"
  $log = { param($m) try { Add-Content -Path $logf -Value ("{0}  {1}" -f (Get-Date -Format s), $m) } catch {} }

  # Condense the transcript and summarize via headless claude.
  if (-not $hook.transcript_path -or -not (Test-Path $hook.transcript_path)) { & $log "bail: no transcript ($slug)"; exit 0 }
  # Digest the transcript to a small text excerpt. Piping the raw tail can be megabytes of
  # tool-result JSON, which stalls `claude -p` past the SessionEnd hook timeout (root cause of
  # earlier silent failures).
  $convo = Get-CondensedTranscript -Path $hook.transcript_path
  if (-not $convo) { & $log "bail: empty digest ($slug)"; exit 0 }
  & $log ("digest slug={0} chars={1}" -f $slug, $convo.Length)
  # Journal language is configurable (default English) so the vault stays single-language even when a
  # session was conducted in another language — `claude -p` otherwise mirrors the transcript's language.
  $lang = "English"
  try {
    if (Test-Path "$brain\_meta\engram.json") {
      $ecfg = Get-Content "$brain\_meta\engram.json" -Raw | ConvertFrom-Json
      if ($ecfg.journal -and $ecfg.journal.language) { $lang = "" + $ecfg.journal.language }
    }
  } catch {}
  $prompt = "You are writing a project journal entry. Summarize the session transcript piped to you into 3-6 terse bullets covering decisions, changes, what's in progress, and TODOs/blockers. Write the entry in $lang regardless of the language used in the transcript. Output ONLY the bullets (each starting with '- '), no preamble or heading."
  $env:BRAIN_CAPTURE_ACTIVE = "1"   # nested session's SessionEnd hook no-ops (see guard above)
  # `claude -p` emits UTF-8; the console's default OEM codepage (e.g. CP852 on PL Windows) would
  # mangle non-ASCII (Polish diacritics) in the captured stdout. Force UTF-8 decoding of child output.
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  $summary = ($convo | claude -p $prompt 2>$null) -join "`n"
  # strip any stray CLI warning that may leak into stdout, then bail if empty
  $summary = ($summary -replace '(?m)^\s*Warning: no stdin data received.*$', '').Trim()
  if (-not $summary) { & $log "bail: empty summary ($slug)"; exit 0 }

  $date = Get-Date -Format "yyyy-MM-dd HH:mm"
  # Record the git branch the work happened on (best-effort; blank for detached HEAD / non-git cwd).
  $branch = ""
  try { $branch = (& git -C $cwd rev-parse --abbrev-ref HEAD 2>$null) -join "" } catch {}
  $branchTag = if ($branch -and $branch -ne "HEAD") { " - branch: $branch" } else { "" }
  $entry = "## $date - session $($hook.session_id)$branchTag`n$summary`n`n"
  $existing = if (Test-Path $journal) { Get-Content $journal -Raw } else { "" }
  # Insert before the FIRST existing "## " entry so the newest entry leads the entry list without
  # displacing leading frontmatter / title / intro. Plain prepend when there are no entries yet.
  $firstEntry = [regex]::Match($existing, '(?m)^## ')
  if ($firstEntry.Success) {
    $merged = $existing.Substring(0, $firstEntry.Index) + $entry + $existing.Substring($firstEntry.Index)
  } else {
    $merged = $entry + $existing
  }
  Set-Content -Path $journal -Value $merged -Encoding utf8
  & $log ("wrote journal entry: $slug (session $($hook.session_id))")

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
