# hooks/posttooluse-track.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("braintrack_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo") | Out-Null
$env:BRAIN_HOME = $brain
$sid = "track-sess"
try {
  . (Join-Path $here "capture.lib.ps1")

  # 1) edited file is tracked
  $payload = @{ session_id = $sid; tool_name = "Edit"; tool_input = @{ file_path = "C:\proj\backend\auth.py" } } | ConvertTo-Json -Compress
  $payload | pwsh -NoProfile -File (Join-Path $here "posttooluse-track.ps1") | Out-Null
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if (@($s.files) -notcontains "C:\proj\backend\auth.py") { throw "FAIL: edited file not tracked. files=$(@($s.files) -join ',')" }

  # 2) editing journal.md strips THIS session's auto block and sets journalEdited
  $journal = Join-Path $brain "projects\demo\journal.md"
  "# Journal`n" | Set-Content $journal -Encoding utf8
  Set-AutoJournalBlock -JournalPath $journal -SessionId $sid -EntryText "## auto - session $sid`n- draft"
  $j = Get-Content $journal -Raw
  if ($j -notmatch "brain:auto session=$sid") { throw "FAIL: precondition — auto block not present" }
  $payload2 = @{ session_id = $sid; tool_name = "Edit"; tool_input = @{ file_path = $journal } } | ConvertTo-Json -Compress
  $payload2 | pwsh -NoProfile -File (Join-Path $here "posttooluse-track.ps1") | Out-Null
  $j2 = Get-Content $journal -Raw
  if ($j2 -match "brain:auto session=$sid") { throw "FAIL: auto block not stripped on journal edit. $j2" }
  $s2 = Get-SessionScratch -Brain $brain -SessionId $sid
  if (-not $s2.journalEdited) { throw "FAIL: journalEdited not set" }
  "PASS: posttooluse tracks files and strips auto block on journal edit"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_HOME -ErrorAction SilentlyContinue }
