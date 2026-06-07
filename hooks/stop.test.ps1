# hooks/stop.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainstop_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo") | Out-Null
Set-Content (Join-Path $brain "_meta\project-map.json") -Value (@{ "C:\proj\demo" = "demo" } | ConvertTo-Json) -Encoding utf8
$env:BRAIN_HOME = $brain
$env:BRAIN_STOP_THRESHOLD = "3"   # low threshold for the test
$env:BRAIN_NO_SUMMARIZE = "1"     # don't actually call claude -p in the test
$sid = "stop-sess"
try {
  . (Join-Path $here "capture.lib.ps1")
  $payload = @{ session_id = $sid; cwd = "C:\proj\demo"; transcript_path = "" } | ConvertTo-Json -Compress
  1..2 | ForEach-Object { $payload | pwsh -NoProfile -File (Join-Path $here "stop.ps1") | Out-Null }
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if ([int]$s.turns -ne 2) { throw "FAIL: expected 2 turns, got $($s.turns)" }
  if ($s.thresholdHit) { throw "FAIL: threshold should not be hit at 2 < 3" }

  $payload | pwsh -NoProfile -File (Join-Path $here "stop.ps1") | Out-Null  # 3rd turn -> threshold
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if (-not $s.thresholdHit) { throw "FAIL: threshold flag not set at turns=3" }
  "PASS: stop hook accumulates turns and flags threshold"
}
finally {
  Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item Env:BRAIN_HOME, Env:BRAIN_STOP_THRESHOLD, Env:BRAIN_NO_SUMMARIZE -ErrorAction SilentlyContinue
}
