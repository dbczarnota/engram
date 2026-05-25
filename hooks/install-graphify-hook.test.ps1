# Test: Install-GraphifyHook writes a working post-commit hook that calls the graphify CLI
# directly (LF line endings, idempotent, and refuses to clobber a foreign post-commit hook).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "install-graphify-hook.ps1")

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("graphhook_" + [Guid]::NewGuid().ToString("N"))
try {
  $null = git init -q $tmp
  $hookPath = Join-Path $tmp ".git\hooks\post-commit"

  # fresh install
  Install-GraphifyHook -RepoPath $tmp | Out-Null
  if (-not (Test-Path $hookPath)) { throw "FAIL: post-commit not written" }
  $raw = [IO.File]::ReadAllText($hookPath)
  if ($raw -notmatch 'graphify update \.') { throw "FAIL: hook does not call 'graphify update .'" }
  if ($raw -match "`r") { throw "FAIL: hook has CRLF; sh needs LF" }

  # idempotent: second install does not stack content
  Install-GraphifyHook -RepoPath $tmp | Out-Null
  $raw2 = [IO.File]::ReadAllText($hookPath)
  if ($raw2 -ne $raw) { throw "FAIL: not idempotent" }
  if (([regex]::Matches($raw2, 'graphify update \.')).Count -ne 1) { throw "FAIL: hook body duplicated" }

  # refuses to clobber a foreign (non-graphify) post-commit hook
  Set-Content -LiteralPath $hookPath -Value "#!/bin/sh`necho mine" -Encoding ascii
  $threw = $false
  try { Install-GraphifyHook -RepoPath $tmp | Out-Null } catch { $threw = $true }
  if (-not $threw) { throw "FAIL: clobbered a foreign post-commit hook" }
  if ((Get-Content $hookPath -Raw) -notmatch "echo mine") { throw "FAIL: foreign hook was overwritten" }

  "PASS: writes LF hook calling graphify CLI, idempotent, protects foreign hooks"
}
finally {
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
