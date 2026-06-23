# Test: Install-CrgHook writes a working post-commit hook that calls the code-review-graph CLI
# directly (LF line endings, idempotent, and refuses to clobber a foreign post-commit hook).
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $here "install-crg-hook.ps1")

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("crghook_" + [Guid]::NewGuid().ToString("N"))
try {
  $null = git init -q $tmp
  $hookPath = Join-Path $tmp ".git\hooks\post-commit"

  # fresh install
  Install-CrgHook -RepoPath $tmp | Out-Null
  if (-not (Test-Path $hookPath)) { throw "FAIL: post-commit not written" }
  $raw = [IO.File]::ReadAllText($hookPath)
  if ($raw -notmatch 'code-review-graph update') { throw "FAIL: hook does not call 'code-review-graph update'" }
  if ($raw -match 'graphify') { throw "FAIL: hook still references graphify" }
  if ($raw -notmatch 'crg-prune') { throw "FAIL: hook missing self-heal prune" }
  if ($raw -match "`r") { throw "FAIL: hook has CRLF; sh needs LF" }

  # idempotent: second install does not stack content
  Install-CrgHook -RepoPath $tmp | Out-Null
  $raw2 = [IO.File]::ReadAllText($hookPath)
  if ($raw2 -ne $raw) { throw "FAIL: not idempotent" }
  if (([regex]::Matches($raw2, 'code-review-graph update')).Count -ne 1) { throw "FAIL: hook body duplicated" }

  # replaces a retired graphify-era hook (contains 'graphify') — our own past marker
  Set-Content -LiteralPath $hookPath -Value "#!/bin/sh`n# graphify auto-rebuild`ngraphify update ." -Encoding ascii
  Install-CrgHook -RepoPath $tmp | Out-Null
  if ((Get-Content $hookPath -Raw) -match 'graphify') { throw "FAIL: did not replace retired graphify hook" }

  # refuses to clobber a truly foreign post-commit hook
  Set-Content -LiteralPath $hookPath -Value "#!/bin/sh`necho mine" -Encoding ascii
  $threw = $false
  try { Install-CrgHook -RepoPath $tmp | Out-Null } catch { $threw = $true }
  if (-not $threw) { throw "FAIL: clobbered a foreign post-commit hook" }
  if ((Get-Content $hookPath -Raw) -notmatch "echo mine") { throw "FAIL: foreign hook was overwritten" }

  "PASS: writes LF CRG-only hook with prune, idempotent, replaces graphify-era hook, protects foreign hooks"
}
finally {
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
