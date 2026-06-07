# hooks/feature-match.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "capture.lib.ps1")
$brain = Join-Path ([IO.Path]::GetTempPath()) ("brainfm_" + [Guid]::NewGuid().ToString("N"))
$fdir = Join-Path $brain "projects\demo\features"
New-Item -ItemType Directory -Force $fdir | Out-Null
try {
  Set-Content "$fdir\fact-extraction.md" -Encoding utf8 -Value @"
---
type: feature
files: ["backend/agents/extraction.py", "backend/api/editor_facts.py"]
---
# Fact extraction
"@
  Set-Content "$fdir\modal.md" -Encoding utf8 -Value @"
---
type: feature
files: ["frontend/Modal.tsx"]
---
# Modal
"@
  $m = Find-MatchingFeature -Brain $brain -Slug "demo" -Files @("C:\code\proj\backend\agents\extraction.py")
  if ($m -ne "fact-extraction") { throw "FAIL: expected fact-extraction, got '$m'" }

  $none = Find-MatchingFeature -Brain $brain -Slug "demo" -Files @("C:\code\proj\README.md")
  if ($none) { throw "FAIL: expected no match, got '$none'" }

  "PASS: matcher intersects session files with feature files: by suffix"
}
finally { Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue }
