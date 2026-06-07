# hooks/sessionstart.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainss_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "lessons\_inbox") | Out-Null
Set-Content (Join-Path $brain "lessons\_inbox\2026-06-07-foo.md") -Value "draft" -Encoding utf8
$env:BRAIN_HOME = $brain
try {
  $payload = @{ session_id = "s1"; cwd = "C:\whatever" } | ConvertTo-Json -Compress
  $out = $payload | pwsh -NoProfile -File (Join-Path $here "sessionstart.ps1")
  if ($out -notmatch "lesson draft") { throw "FAIL: expected pending-draft notice. Got: $out" }
  if ($out -notmatch "additionalContext") { throw "FAIL: not emitted as hook context JSON" }
  "PASS: sessionstart notifies pending drafts"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_HOME -ErrorAction SilentlyContinue }
