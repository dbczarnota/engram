# Test: capture.ps1 is a no-op when cwd is not a known project.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $here "capture.ps1"

# hook payload with NO matching project for C:\nowhere
$payload = @{ cwd = "C:\nowhere"; transcript_path = "C:\nonexistent.jsonl"; session_id = "test1" } | ConvertTo-Json -Compress
$out = $payload | pwsh -NoProfile -File $script 2>&1
if ($LASTEXITCODE -ne 0) { throw "expected exit 0 for unknown project, got $LASTEXITCODE : $out" }
"PASS: no-op on unknown project"
