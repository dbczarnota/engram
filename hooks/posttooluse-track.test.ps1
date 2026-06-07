# hooks/posttooluse-track.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("braintrack_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
$env:BRAIN_HOME = $brain
$sid = "track-sess"
try {
  $payload = @{ session_id = $sid; tool_name = "Edit"; tool_input = @{ file_path = "C:\proj\backend\auth.py" } } | ConvertTo-Json -Compress
  $payload | pwsh -NoProfile -File (Join-Path $here "posttooluse-track.ps1") | Out-Null

  . (Join-Path $here "capture.lib.ps1")
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if (@($s.files) -notcontains "C:\proj\backend\auth.py") { throw "FAIL: edited file not tracked. files=$(@($s.files) -join ',')" }
  "PASS: posttooluse hook tracks edited files"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_HOME -ErrorAction SilentlyContinue }
