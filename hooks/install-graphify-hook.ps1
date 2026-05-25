#requires -Version 7
# Install a *working* graphify auto-rebuild post-commit hook into a git repo.
#
# Why this exists: the upstream `graphify hook install` writes a hook that locates a Python
# interpreter and runs `from graphify.watch import _rebuild_code`. On a uv-tool / Windows install
# that silently fails — `graphify` is a .exe shim (no shebang to parse) and the isolated tool venv
# isn't importable by the system Python — so the hook hits `exit 0` and the graph never rebuilds.
# We call the `graphify` CLI directly instead (it works), code-only + incremental, best-effort.
#
# Usage:  . install-graphify-hook.ps1; Install-GraphifyHook -RepoPath C:\path\to\repo

$script:GraphifyHookBody = @'
#!/bin/sh
# engram graphify auto-rebuild (installed by hooks/install-graphify-hook.ps1).
# Calls the graphify CLI directly — the upstream hook no-ops on uv-tool/Windows installs.
# Incremental + code-only (cached, no LLM); never blocks the commit on failure.
command -v graphify >/dev/null 2>&1 || exit 0
mkdir -p "$HOME/.cache" 2>/dev/null
graphify update . >> "$HOME/.cache/graphify-rebuild.log" 2>&1 || true
exit 0
'@

function Install-GraphifyHook {
  param([string]$RepoPath = ".")
  $gitDir = (& git -C $RepoPath rev-parse --absolute-git-dir 2>$null)
  if (-not $gitDir) { throw "not a git repo: $RepoPath" }
  $hooksDir = Join-Path $gitDir "hooks"
  New-Item -ItemType Directory -Force $hooksDir | Out-Null
  $hookPath = Join-Path $hooksDir "post-commit"

  # Don't clobber a foreign post-commit hook (ours and the upstream graphify one both say "graphify").
  if (Test-Path $hookPath) {
    $existing = [IO.File]::ReadAllText($hookPath)
    if ($existing -notmatch 'graphify') {
      throw "refusing to overwrite a non-graphify post-commit hook at $hookPath"
    }
  }

  # Write LF endings — Git for Windows runs hooks through sh, which chokes on CRLF.
  $body = $script:GraphifyHookBody -replace "`r`n", "`n"
  [IO.File]::WriteAllText($hookPath, $body, [Text.UTF8Encoding]::new($false))
  return $hookPath
}
