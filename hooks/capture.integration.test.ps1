# Integration test: capture.ps1 writes a journal entry for a KNOWN project.
# Uses a throwaway BRAIN_HOME and a fake `claude` shim so nothing real is touched
# and no real LLM call is made.
$ErrorActionPreference = "Stop"
$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "capture.ps1"

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("braintest_" + [Guid]::NewGuid().ToString("N"))
try {
  # --- fake vault ---
  $proj = "demoproj"
  $cwd  = Join-Path $tmp "code\$proj"
  New-Item -ItemType Directory -Force "$tmp\_meta"            | Out-Null
  New-Item -ItemType Directory -Force "$tmp\projects\$proj"   | Out-Null
  New-Item -ItemType Directory -Force $cwd                    | Out-Null
  New-Item -ItemType Directory -Force "$tmp\bin"              | Out-Null

  (@{ $cwd = $proj } | ConvertTo-Json) | Set-Content "$tmp\_meta\project-map.json" -Encoding utf8
  "# Journal`n" | Set-Content "$tmp\projects\$proj\journal.md" -Encoding utf8

  # fake transcript: realistic JSONL (the condenser parses these; plain text would be skipped)
  $tlines = @(
    (@{ type = "user";      message = @{ role = "user";      content = "add a retry helper" } } | ConvertTo-Json -Compress -Depth 6)
    (@{ type = "assistant"; message = @{ role = "assistant"; content = @(@{ type = "text"; text = "Added retryOperation with 3 attempts." }) } } | ConvertTo-Json -Compress -Depth 6)
  )
  Set-Content -Path "$tmp\transcript.jsonl" -Value $tlines -Encoding utf8

  # fake `claude` shim that ignores stdin and prints a canned summary
  "@echo off`r`necho - integration summary bullet" | Set-Content "$tmp\bin\claude.cmd" -Encoding ascii

  # --- run the hook as a child process (inherits env we set here) ---
  $env:BRAIN_HOME = $tmp
  $env:PATH       = "$tmp\bin;$env:PATH"
  $payload = @{ cwd = $cwd; transcript_path = "$tmp\transcript.jsonl"; session_id = "itest" } | ConvertTo-Json -Compress
  $out = $payload | pwsh -NoProfile -File $script 2>&1
  if ($LASTEXITCODE -ne 0) { throw "hook exited $LASTEXITCODE : $out" }

  $journal = Get-Content "$tmp\projects\$proj\journal.md" -Raw
  if ($journal -notmatch "integration summary bullet") { throw "journal missing summary. Content:`n$journal" }
  if ($journal -notmatch "session itest")              { throw "journal missing session header. Content:`n$journal" }

  "PASS: hook resolved project, called (stubbed) claude, prepended journal entry"
}
finally {
  Remove-Item Env:\BRAIN_HOME -ErrorAction SilentlyContinue
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
