# hooks/gotcha-draft.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainglh_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "lessons\_inbox") | Out-Null
$tx = Join-Path $brain "t.jsonl"
@(@{ type="user"; message=@{ role="user"; content="why does the git hook silently fail on windows" } } | ConvertTo-Json -Compress) | Set-Content $tx -Encoding utf8

$env:BRAIN_CLAUDE_SHIM = "LESSON: windows-git-hooks`n- How to spot it: hook never runs`n- The trap: CRLF endings`n- The fix: write LF"
try {
  Invoke-GotchaDraft -Brain $brain -Slug "demo" -SessionId "s1" -TranscriptPath $tx
  $drafts = Get-ChildItem (Join-Path $brain "lessons\_inbox") -Filter *.md
  if ($drafts.Count -ne 1) { throw "FAIL: expected 1 draft, got $($drafts.Count)" }
  $body = Get-Content $drafts[0].FullName -Raw
  if ($body -notmatch "status: draft") { throw "FAIL: draft missing status:draft frontmatter" }
  if ($body -notmatch "windows-git-hooks") { throw "FAIL: draft missing lesson body" }
  "PASS: gotcha detector writes a draft to lessons/_inbox"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_CLAUDE_SHIM -ErrorAction SilentlyContinue }
