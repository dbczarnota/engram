# hooks/capture.upsert.test.ps1
# Upsert replaces a session's auto block in place (never appends a second).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainups_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo") | Out-Null
$journal = Join-Path $brain "projects\demo\journal.md"
"# Journal`n`n## 2026-01-01 00:00 - session old`n- prior entry`n" | Set-Content $journal -Encoding utf8
try {
  Set-AutoJournalBlock -JournalPath $journal -SessionId "s1" -EntryText "## now - session s1`n- first summary"
  Set-AutoJournalBlock -JournalPath $journal -SessionId "s1" -EntryText "## now - session s1`n- second summary"
  $j = Get-Content $journal -Raw
  $open = ([regex]::Matches($j, [regex]::Escape("<!-- brain:auto session=s1 -->"))).Count
  if ($open -ne 1) { throw "FAIL: expected exactly 1 auto block, got $open. $j" }
  if ($j -match "first summary") { throw "FAIL: old content not replaced. $j" }
  if ($j -notmatch "second summary") { throw "FAIL: new content missing. $j" }
  if ($j -notmatch "prior entry") { throw "FAIL: unrelated entry clobbered. $j" }

  Remove-AutoJournalBlock -JournalPath $journal -SessionId "s1"
  $j2 = Get-Content $journal -Raw
  if ($j2 -match "brain:auto session=s1") { throw "FAIL: block not removed. $j2" }
  if ($j2 -notmatch "prior entry") { throw "FAIL: removal clobbered unrelated entry. $j2" }
  "PASS: upsert replaces in place and removal is clean"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue }
