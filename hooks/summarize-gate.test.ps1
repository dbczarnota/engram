# hooks/summarize-gate.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("braingate_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
$sid = "gate-sess"
try {
  if (Test-ShouldSummarize -Brain $brain -SessionId $sid) { throw "FAIL: empty session should not summarize" }

  Add-ScratchFile -Brain $brain -SessionId $sid -File "backend/auth.py"
  if (-not (Test-ShouldSummarize -Brain $brain -SessionId $sid)) { throw "FAIL: edited session should summarize" }

  Set-ScratchFlag -Brain $brain -SessionId $sid -Name "summarized" -Value $true
  if (Test-ShouldSummarize -Brain $brain -SessionId $sid) { throw "FAIL: summarized session must not re-summarize" }

  Set-ScratchFlag -Brain $brain -SessionId $sid -Name "summarized" -Value $false
  Add-ScratchFile -Brain $brain -SessionId $sid -File "projects/x/journal.md"
  if (Test-ShouldSummarize -Brain $brain -SessionId $sid) { throw "FAIL: manual checkpoint must suppress auto" }

  "PASS: summarize gate honors work/dedup/checkpoint"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue }
