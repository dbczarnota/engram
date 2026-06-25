# hooks/stop.test.ps1
# Stop accumulates turns (cheap, no LLM) and does not capture below the first threshold.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainstop_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo") | Out-Null
Set-Content (Join-Path $brain "_meta\project-map.json") -Value (@{ "C:\proj\demo" = "demo" } | ConvertTo-Json) -Encoding utf8
$env:BRAIN_HOME = $brain
$env:BRAIN_NO_SUMMARIZE = "1"   # never call the summarizer in this test
$sid = "stop-sess"
try {
  . (Join-Path $here "capture.lib.ps1")
  $payload = @{ session_id = $sid; cwd = "C:\proj\demo"; transcript_path = "" } | ConvertTo-Json -Compress
  1..3 | ForEach-Object { $payload | pwsh -NoProfile -File (Join-Path $here "stop.ps1") | Out-Null }
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if ([int]$s.turns -ne 3) { throw "FAIL: expected 3 turns, got $($s.turns)" }
  if ($s.everSummarized) { throw "FAIL: must not summarize with BRAIN_NO_SUMMARIZE set" }
  "PASS: stop hook accumulates turns without summarizing"
}
finally {
  Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item Env:BRAIN_HOME, Env:BRAIN_NO_SUMMARIZE -ErrorAction SilentlyContinue
}
