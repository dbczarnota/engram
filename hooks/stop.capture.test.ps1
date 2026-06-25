# hooks/stop.capture.test.ps1
# A short editing session (no commit) is captured at the first threshold via an upserted auto block.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainstopcap_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
New-Item -ItemType Directory -Force (Join-Path $brain "projects\demo\features") | Out-Null
Set-Content (Join-Path $brain "_meta\project-map.json") -Value (@{ "C:\proj\demo" = "demo" } | ConvertTo-Json) -Encoding utf8
Set-Content (Join-Path $brain "_meta\engram.json") -Value '{ "journal": { "language": "English" } }' -Encoding utf8
"# Journal`n" | Set-Content (Join-Path $brain "projects\demo\journal.md") -Encoding utf8
$tx = Join-Path $brain "t.jsonl"
@(@{ type="user"; message=@{ role="user"; content="do the work" } } | ConvertTo-Json -Compress) | Set-Content $tx -Encoding utf8
$env:BRAIN_HOME = $brain
$env:BRAIN_SEM_DIR = (Join-Path (Split-Path $here) "_meta\semantic")
$env:BRAIN_SUMMARIZE_SHIM = '{"journal":"- shipped the thing"}'
$env:BRAIN_FIRST_THRESHOLD = "8"
$env:BRAIN_REFRESH_THRESHOLD = "25"
$env:BRAIN_REINDEX_SHIM = (Join-Path $brain "reindex.log")  # don't run real uv
$sid = "shortsess"
try {
  # Mark real work (an edited file) so the gate passes, then drive turns via the hook.
  Add-ScratchFile -Brain $brain -SessionId $sid -File "C:\proj\demo\app.py"
  $payload = @{ session_id = $sid; cwd = "C:\proj\demo"; transcript_path = $tx } | ConvertTo-Json -Compress

  1..7 | ForEach-Object { $payload | pwsh -NoProfile -File (Join-Path $here "stop.ps1") | Out-Null }
  $j = Get-Content (Join-Path $brain "projects\demo\journal.md") -Raw
  if ($j -match "brain:auto session=$sid") { throw "FAIL: captured before first threshold (turns=7)" }

  $payload | pwsh -NoProfile -File (Join-Path $here "stop.ps1") | Out-Null   # turn 8 -> first capture
  $j = Get-Content (Join-Path $brain "projects\demo\journal.md") -Raw
  $blocks = ([regex]::Matches($j, [regex]::Escape("<!-- brain:auto session=$sid -->"))).Count
  if ($blocks -ne 1) { throw "FAIL: expected 1 auto block at turns=8, got $blocks. $j" }
  if ($j -notmatch "shipped the thing") { throw "FAIL: summary text missing. $j" }
  $s = Get-SessionScratch -Brain $brain -SessionId $sid
  if (-not $s.everSummarized) { throw "FAIL: everSummarized not set" }
  if ([int]$s.turns -ne 0) { throw "FAIL: turns not reset after capture, got $($s.turns)" }
  "PASS: short session captured at first threshold via single upsert block"
}
finally {
  Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item Env:BRAIN_HOME, Env:BRAIN_SEM_DIR, Env:BRAIN_SUMMARIZE_SHIM, Env:BRAIN_FIRST_THRESHOLD, Env:BRAIN_REFRESH_THRESHOLD, Env:BRAIN_REINDEX_SHIM -ErrorAction SilentlyContinue
}
