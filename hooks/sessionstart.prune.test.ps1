# hooks/sessionstart.prune.test.ps1
# SessionStart removes session-*.json older than 14 days, keeps fresh ones.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainprune_" + [Guid]::NewGuid().ToString("N"))
$state = Join-Path $brain "_meta\state"
New-Item -ItemType Directory -Force $state | Out-Null
New-Item -ItemType Directory -Force (Join-Path $brain "lessons\_inbox") | Out-Null
$env:BRAIN_HOME = $brain
$old = Join-Path $state "session-old.json"; "{}" | Set-Content $old -Encoding utf8
$new = Join-Path $state "session-new.json"; "{}" | Set-Content $new -Encoding utf8
(Get-Item $old).LastWriteTime = (Get-Date).AddDays(-30)
try {
  "" | pwsh -NoProfile -File (Join-Path $here "sessionstart.ps1") | Out-Null
  if (Test-Path $old) { throw "FAIL: 30-day-old scratch not pruned" }
  if (-not (Test-Path $new)) { throw "FAIL: fresh scratch wrongly pruned" }
  "PASS: sessionstart prunes stale scratch, keeps fresh"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_HOME -ErrorAction SilentlyContinue }
