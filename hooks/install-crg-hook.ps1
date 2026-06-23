#requires -Version 7
# Install a *working* code-review-graph (CRG) auto-rebuild post-commit hook into a git repo.
#
# Why this exists: CRG's incremental `update` keeps the per-repo `.code-review-graph/graph.db` fresh, but
# on Windows its `update` path feeds backslash file paths to CRG's POSIX `node_modules/**` ignore matcher
# (_should_ignore), so it re-adds every dependency + .claude/worktree file each commit (a full `build`
# normalizes separators and stays clean — `update` does not). This hook runs `update` then a self-heal
# prune so the graph stays app-only every commit. Best-effort; never blocks the commit.
#
# (This replaced an earlier graphify-based hook — graphify was ~90% redundant with CRG for code
# structure, so the setup standardized on CRG alone for the agent-facing code graph.)
#
# Usage:  . install-crg-hook.ps1; Install-CrgHook -RepoPath C:\path\to\repo

$script:CrgHookBody = @'
#!/bin/sh
# CRG code-graph auto-rebuild (installed by hooks/install-crg-hook.ps1).
# Incremental AST update + self-heal prune, code-only, best-effort; never blocks the commit.
mkdir -p "$HOME/.cache" 2>/dev/null
# CRG: fast lookup graph (.code-review-graph/graph.db) — incremental AST. Semantic embeddings are NOT
# refreshed here (too heavy per-commit); run `code-review-graph embed` periodically for new nodes.
command -v code-review-graph >/dev/null 2>&1 && code-review-graph update >> "$HOME/.cache/crg-rebuild.log" 2>&1 || true
# CRG self-heal: on Windows the `update` path feeds backslash file paths to CRG's POSIX
# `node_modules/**` ignore matcher (_should_ignore), so it re-adds every dependency file each commit
# (a full `build` normalizes separators and stays clean — `update` does not). Prune dependency
# nodes/edges + orphaned rows and rebuild FTS so the graph stays app-only. Best-effort, never blocks.
command -v python >/dev/null 2>&1 && python - >> "$HOME/.cache/crg-rebuild.log" 2>&1 <<'PY' || true
import os, sqlite3, sys
db = os.path.join(".code-review-graph", "graph.db")
if not os.path.exists(db):
    sys.exit(0)
PATS = ("%node_modules%", "%site-packages%", "%.claude%")  # deps + git-worktree source copies under .claude/
where = " OR ".join("file_path LIKE ?" for _ in PATS)
con = sqlite3.connect(db)
try:
    n = con.execute(f"SELECT COUNT(*) FROM nodes WHERE {where}", PATS).fetchone()[0]
    if n:
        con.execute(f"DELETE FROM edges WHERE {where}", PATS)
        con.execute(f"DELETE FROM nodes WHERE {where}", PATS)
        for stmt in (
            "DELETE FROM embeddings WHERE qualified_name NOT IN (SELECT qualified_name FROM nodes)",
            "DELETE FROM risk_index WHERE node_id NOT IN (SELECT id FROM nodes)",
            "DELETE FROM flow_memberships WHERE node_id NOT IN (SELECT id FROM nodes)",
            "INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')",
        ):
            try:
                con.execute(stmt)
            except sqlite3.OperationalError:
                pass
        con.commit()
        print(f"[crg-prune] removed {n} dependency nodes from {db}")
finally:
    con.close()
PY
exit 0
'@

function Install-CrgHook {
  param([string]$RepoPath = ".")
  $gitDir = (& git -C $RepoPath rev-parse --absolute-git-dir 2>$null)
  if (-not $gitDir) { throw "not a git repo: $RepoPath" }
  $hooksDir = Join-Path $gitDir "hooks"
  New-Item -ItemType Directory -Force $hooksDir | Out-Null
  $hookPath = Join-Path $hooksDir "post-commit"

  # Don't clobber a foreign post-commit hook. Accept our own past markers: the current CRG hook
  # ('code-review-graph') and the retired graphify-era hook ('graphify') we are replacing.
  if (Test-Path $hookPath) {
    $existing = [IO.File]::ReadAllText($hookPath)
    if ($existing -notmatch 'code-review-graph|graphify') {
      throw "refusing to overwrite a non-CRG post-commit hook at $hookPath"
    }
  }

  # Write LF endings — Git for Windows runs hooks through sh, which chokes on CRLF.
  $body = $script:CrgHookBody -replace "`r`n", "`n"
  [IO.File]::WriteAllText($hookPath, $body, [Text.UTF8Encoding]::new($false))
  return $hookPath
}
