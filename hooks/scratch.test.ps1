# hooks/scratch.test.ps1
# Test: session scratch accumulates turns/files/flags and round-trips through JSON.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")

$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainscratch_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
$sid = "test-session-1"
try {
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if ($s.turns -ne 0) { throw "FAIL: new scratch turns should be 0, got $($s.turns)" }

  Add-ScratchTurn -Brain $brain -SessionId $sid -Prompt "fix the auth bug"
  Add-ScratchFile -Brain $brain -SessionId $sid -File "backend/auth.py"
  Add-ScratchFile -Brain $brain -SessionId $sid -File "backend/auth.py"   # dedup
  Set-ScratchFlag -Brain $brain -SessionId $sid -Name "committed" -Value $true

  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if ($s.turns -ne 1)              { throw "FAIL: turns should be 1, got $($s.turns)" }
  if (@($s.files).Count -ne 1)     { throw "FAIL: files should dedup to 1, got $(@($s.files).Count)" }
  if (-not $s.committed)           { throw "FAIL: committed flag not set" }
  if (@($s.prompts)[-1] -ne "fix the auth bug") { throw "FAIL: last prompt not recorded" }

  Clear-SessionScratch -Brain $brain -SessionId $sid
  if (Test-Path (Join-Path $brain "_meta\state\session-$sid.json")) { throw "FAIL: scratch not cleared" }

  "PASS: scratch accumulates and clears"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue }
