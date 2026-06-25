# hooks/reindex.throttle.test.ps1
# Two reindex calls within the throttle window run the body only once.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainrx_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
$log = Join-Path $brain "reindex.log"
$env:BRAIN_REINDEX_SHIM = $log
$sid = "rx-sess"
try {
  Invoke-Reindex -Brain $brain -SessionId $sid -ThrottleMinutes 10
  Invoke-Reindex -Brain $brain -SessionId $sid -ThrottleMinutes 10   # within window -> skipped
  $n = @(Get-Content $log -ErrorAction SilentlyContinue).Count
  if ($n -ne 1) { throw "FAIL: expected 1 reindex within window, got $n" }

  # Force the window open by backdating lastReindexAt, then it runs again.
  Set-ScratchFlag -Brain $brain -SessionId $sid -Name "lastReindexAt" -Value ((Get-Date).AddMinutes(-20).ToString("o"))
  Invoke-Reindex -Brain $brain -SessionId $sid -ThrottleMinutes 10
  $n2 = @(Get-Content $log -ErrorAction SilentlyContinue).Count
  if ($n2 -ne 2) { throw "FAIL: expected 2 reindex after window reopened, got $n2" }
  "PASS: reindex throttles within the window and runs after it reopens"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_REINDEX_SHIM -ErrorAction SilentlyContinue }
