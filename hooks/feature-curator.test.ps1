# hooks/feature-curator.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainfc_" + [Guid]::NewGuid().ToString("N"))
$fdir = Join-Path $brain "projects\demo\features"
New-Item -ItemType Directory -Force $fdir | Out-Null
$tx = Join-Path $brain "t.jsonl"
@(@{ type="user"; message=@{ role="user"; content="build the fact gate" } } | ConvertTo-Json -Compress) | Set-Content $tx -Encoding utf8
try {
  # NEW feature path (no match)
  $env:BRAIN_CLAUDE_SHIM = "FEATURE: fact-gate`n## What it does`nGates facts before writing."
  Invoke-FeatureCurator -Brain $brain -Slug "demo" -SessionId "s1" -TranscriptPath $tx -Files @("C:\code\proj\backend\gate.py") -Branch "feat/fact-gate"
  $drafts = @(Get-ChildItem (Join-Path $fdir "_inbox") -Filter *.md -ErrorAction SilentlyContinue)
  if ($drafts.Count -ne 1) { throw "FAIL: expected 1 draft, got $($drafts.Count)" }
  $body = Get-Content $drafts[0].FullName -Raw
  if ($body -notmatch "type: feature-draft") { throw "FAIL: missing draft frontmatter" }
  if ($body -notmatch "fact-gate") { throw "FAIL: missing feature body" }

  # UPDATE path (matches an existing feature by files)
  Set-Content "$fdir\gate.md" -Encoding utf8 -Value @"
---
type: feature
files: ["backend/gate.py"]
---
# Gate
"@
  $env:BRAIN_CLAUDE_SHIM = "UPDATE: gate`n## How it's built`nNow async."
  Invoke-FeatureCurator -Brain $brain -Slug "demo" -SessionId "s2" -TranscriptPath $tx -Files @("C:\code\proj\backend\gate.py") -Branch ""
  $upd = @(Get-ChildItem (Join-Path $fdir "_inbox") -Filter *.md | Where-Object { (Get-Content $_.FullName -Raw) -match "updates: gate" })
  if ($upd.Count -lt 1) { throw "FAIL: expected an update draft with 'updates: gate'" }

  # NONE path writes nothing
  $before = @(Get-ChildItem (Join-Path $fdir "_inbox") -Filter *.md).Count
  $env:BRAIN_CLAUDE_SHIM = "NONE"
  Invoke-FeatureCurator -Brain $brain -Slug "demo" -SessionId "s3" -TranscriptPath $tx -Files @("C:\code\proj\backend\gate.py") -Branch ""
  $after = @(Get-ChildItem (Join-Path $fdir "_inbox") -Filter *.md).Count
  if ($after -ne $before) { throw "FAIL: NONE should write nothing ($before -> $after)" }

  "PASS: feature curator stages new + update drafts, skips NONE"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item Env:BRAIN_CLAUDE_SHIM -ErrorAction SilentlyContinue }
