# Test: the recursion guard. When BRAIN_CAPTURE_ACTIVE is set (i.e. we're already inside a
# capture's nested `claude -p` sub-session), capture.ps1 must no-op immediately and write nothing.
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "capture.ps1"

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("braintest_" + [Guid]::NewGuid().ToString("N"))
try {
  $proj = "demoproj"; $cwd = Join-Path $tmp "code\$proj"
  New-Item -ItemType Directory -Force "$tmp\_meta"          | Out-Null
  New-Item -ItemType Directory -Force "$tmp\projects\$proj" | Out-Null
  New-Item -ItemType Directory -Force $cwd                  | Out-Null
  (@{ $cwd = $proj } | ConvertTo-Json) | Set-Content "$tmp\_meta\project-map.json" -Encoding utf8
  "# Journal`n" | Set-Content "$tmp\projects\$proj\journal.md" -Encoding utf8
  "x" | Set-Content "$tmp\transcript.jsonl" -Encoding utf8

  $env:BRAIN_HOME = $tmp
  $env:BRAIN_CAPTURE_ACTIVE = "1"   # simulate being inside a nested capture
  $payload = @{ cwd = $cwd; transcript_path = "$tmp\transcript.jsonl"; session_id = "guard" } | ConvertTo-Json -Compress
  $payload | pwsh -NoProfile -File $script | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "guard run exited $LASTEXITCODE" }

  $journal = Get-Content "$tmp\projects\$proj\journal.md" -Raw
  if ($journal -match "session guard") { throw "guard FAILED: journal was written despite BRAIN_CAPTURE_ACTIVE" }
  if (Test-Path "$tmp\hooks\hook-fired.log") { throw "guard FAILED: heartbeat written (guard should precede it)" }
  "PASS: guard no-ops when BRAIN_CAPTURE_ACTIVE is set (no write, no heartbeat)"
}
finally {
  Remove-Item Env:\BRAIN_HOME -ErrorAction SilentlyContinue
  Remove-Item Env:\BRAIN_CAPTURE_ACTIVE -ErrorAction SilentlyContinue
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
