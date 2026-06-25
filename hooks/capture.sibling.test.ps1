# hooks/capture.sibling.test.ps1
# Regression: two different sessions' auto blocks must be inserted as siblings (newest-on-top),
# never nested. The old insert logic found the first ^## inside a prior session's block and
# inserted the new block there, breaking the outer block structure.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainsib_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo") | Out-Null
$journal = Join-Path $brain "projects\demo\journal.md"
"# Journal`n`n## 2026-01-01 00:00 - manual entry`n- hand-written`n" | Set-Content $journal -Encoding utf8
try {
  # Write sessA first (older session — e.g. left behind by VS Code which never fires SessionEnd)
  Set-AutoJournalBlock -JournalPath $journal -SessionId "sessA" -EntryText "## 2026-01-01 10:00 - session sessA`n- work by A"
  # Write sessB second (the new session)
  Set-AutoJournalBlock -JournalPath $journal -SessionId "sessB" -EntryText "## 2026-01-01 11:00 - session sessB`n- work by B"

  $j = Get-Content $journal -Raw

  # 1. Exactly one open marker per session
  $countA = ([regex]::Matches($j, [regex]::Escape("<!-- brain:auto session=sessA -->"))).Count
  $countB = ([regex]::Matches($j, [regex]::Escape("<!-- brain:auto session=sessB -->"))).Count
  if ($countA -ne 1) { throw "FAIL: expected exactly 1 sessA block, got $countA.`n$j" }
  if ($countB -ne 1) { throw "FAIL: expected exactly 1 sessB block, got $countB.`n$j" }

  # 2. sessB must NOT be nested inside sessA's block (the nesting bug).
  $openA  = $j.IndexOf('<!-- brain:auto session=sessA -->')
  $closeA = $j.IndexOf('<!-- /brain:auto session=sessA -->')
  if ($openA -lt 0 -or $closeA -lt 0) { throw "FAIL: sessA markers missing.`n$j" }
  $insideA = $j.Substring($openA, $closeA - $openA)
  if ($insideA -match 'session=sessB') { throw "FAIL: sessB is nested inside sessA block (nesting bug).`n$j" }

  # 3. Newest-on-top: sessB's open marker must appear before sessA's open marker.
  $openB = $j.IndexOf('<!-- brain:auto session=sessB -->')
  if ($openB -lt 0) { throw "FAIL: sessB open marker missing.`n$j" }
  if ($openB -ge $openA) { throw "FAIL: sessB (index $openB) is not above sessA (index $openA) — not newest-on-top.`n$j" }

  # 4. The manual entry must still be present.
  if ($j -notmatch 'hand-written') { throw "FAIL: manual entry was clobbered.`n$j" }

  "PASS: sibling blocks are correctly ordered (newest-on-top), not nested, manual entry preserved"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue }
