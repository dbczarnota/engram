# Regression test: capture.ps1 inserts the new entry AFTER leading frontmatter/title and BEFORE the
# first existing "## " entry (it must not bury the frontmatter by blind-prepending to the file top).
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "capture.ps1"

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("braintest_" + [Guid]::NewGuid().ToString("N"))
try {
  $proj = "demoproj"
  $cwd  = Join-Path $tmp "code\$proj"
  New-Item -ItemType Directory -Force "$tmp\_meta"          | Out-Null
  New-Item -ItemType Directory -Force "$tmp\projects\$proj" | Out-Null
  New-Item -ItemType Directory -Force $cwd                  | Out-Null
  New-Item -ItemType Directory -Force "$tmp\bin"            | Out-Null

  (@{ $cwd = $proj } | ConvertTo-Json) | Set-Content "$tmp\_meta\project-map.json" -Encoding utf8

  # Journal WITH frontmatter + title + a pre-existing entry.
  $journalPath = "$tmp\projects\$proj\journal.md"
  $orig = @"
---
type: journal
status: active
---

# Demo Journal

## 2026-01-01 00:00 - session old
- earlier entry
"@
  Set-Content -Path $journalPath -Value $orig -Encoding utf8

  $tlines = @(
    (@{ type = "user";      message = @{ role = "user";      content = "do a thing" } } | ConvertTo-Json -Compress -Depth 6)
    (@{ type = "assistant"; message = @{ role = "assistant"; content = @(@{ type = "text"; text = "did the thing" }) } } | ConvertTo-Json -Compress -Depth 6)
  )
  Set-Content -Path "$tmp\transcript.jsonl" -Value $tlines -Encoding utf8
  "@echo off`r`necho - fresh bullet" | Set-Content "$tmp\bin\claude.cmd" -Encoding ascii

  $env:BRAIN_HOME = $tmp
  $env:PATH       = "$tmp\bin;$env:PATH"
  $payload = @{ cwd = $cwd; transcript_path = "$tmp\transcript.jsonl"; session_id = "new" } | ConvertTo-Json -Compress
  $out = $payload | pwsh -NoProfile -File $script 2>&1
  if ($LASTEXITCODE -ne 0) { throw "hook exited $LASTEXITCODE : $out" }

  $j = Get-Content $journalPath -Raw

  # Frontmatter must still be at the very top (not displaced).
  if ($j -notmatch '(?s)\A---\r?\ntype: journal') { throw "frontmatter no longer at file top:`n$j" }
  # New entry must appear, and BEFORE the old entry.
  $iNew = $j.IndexOf("session new")
  $iOld = $j.IndexOf("session old")
  if ($iNew -lt 0) { throw "new entry missing:`n$j" }
  if ($iOld -lt 0) { throw "old entry missing:`n$j" }
  if ($iNew -ge $iOld) { throw "new entry not inserted before old entry (newest-on-top broken):`n$j" }
  # New entry must come AFTER the frontmatter close + title (not above them).
  $iTitle = $j.IndexOf("# Demo Journal")
  if ($iNew -lt $iTitle) { throw "new entry inserted above the title/frontmatter:`n$j" }

  "PASS: entry inserted below frontmatter/title and above the prior entry"
}
finally {
  Remove-Item Env:\BRAIN_HOME -ErrorAction SilentlyContinue
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
