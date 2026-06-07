# hooks/capture.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("braincap_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo\features") | Out-Null
Set-Content (Join-Path $brain "_meta\engram.json") -Value '{ "journal": { "language": "English" } }' -Encoding utf8
"# Journal`n" | Set-Content (Join-Path $brain "projects\demo\journal.md") -Encoding utf8
$tx = Join-Path $brain "t.jsonl"
@(@{ type="user"; message=@{ role="user"; content="build the gate" } } | ConvertTo-Json -Compress) | Set-Content $tx -Encoding utf8
# Point summarize at the real semantic dir (its venv) instead of copying it; shim avoids any backend.
$env:BRAIN_SEM_DIR = (Join-Path (Split-Path $here) "_meta\semantic")
$env:BRAIN_SUMMARIZE_SHIM = '{"journal":"- did the gate","lesson":{"tech":"win-quirk","body":"- spot\n- trap\n- fix"},"feature":{"kind":"FEATURE","name":"gate","body":"## What it does\nGates."}}'
try {
  $wrote = Invoke-Capture -Brain $brain -Slug "demo" -SessionId "s1" -TranscriptPath $tx -Cwd $brain
  if (-not $wrote) { throw "FAIL: expected journal write" }
  $j = Get-Content (Join-Path $brain "projects\demo\journal.md") -Raw
  if ($j -notmatch "did the gate") { throw "FAIL: journal missing summary. $j" }
  if (-not (Get-ChildItem (Join-Path $brain "lessons\_inbox") -Filter *.md)) { throw "FAIL: no lesson draft" }
  if (-not (Get-ChildItem (Join-Path $brain "projects\demo\features\_inbox") -Filter *.md)) { throw "FAIL: no feature draft" }
  "PASS: Invoke-Capture writes journal + lesson draft + feature draft from one JSON"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_SUMMARIZE_SHIM, Env:BRAIN_SEM_DIR -ErrorAction SilentlyContinue }
