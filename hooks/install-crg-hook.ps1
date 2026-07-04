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
# CRG self-heal (best-effort, never blocks). Two Windows-specific fixes the upstream `update` path needs:
#   1) Dependency prune: `update` feeds backslash paths to CRG's POSIX `node_modules/**` ignore matcher
#      (_should_ignore), so it re-adds every dependency / worktree file each commit. Strip them.
#   2) Drive-letter canon: the same file reached as `c:\…` and `C:\…` yields TWO nodes (qualified_name is
#      case-sensitive), doubling the graph and every query. Canonicalize the drive letter to upper-case.
command -v python >/dev/null 2>&1 && python - >> "$HOME/.cache/crg-rebuild.log" 2>&1 <<'PY' || true
import os, sqlite3, sys
db = os.path.join(".code-review-graph", "graph.db")
if not os.path.exists(db):
    sys.exit(0)
PATS = ("%node_modules%", "%site-packages%", "%.venv%", "%.worktrees%", "%.claude%", "%.obsidian%")  # deps, venvs, git-worktree copies (.worktrees + .claude/worktrees), vendored editor plugins
where = " OR ".join("file_path LIKE ?" for _ in PATS)

def canon(s):  # "c:\..." -> "C:\..." (upper-case drive letter only)
    return s[0].upper() + s[1:] if len(s) >= 2 and s[1] == ":" and "a" <= s[0] <= "z" else s

con = sqlite3.connect(db)
changed = False
try:
    pruned = con.execute(f"SELECT COUNT(*) FROM nodes WHERE {where}", PATS).fetchone()[0]
    if pruned:
        con.execute(f"DELETE FROM edges WHERE {where}", PATS)
        con.execute(f"DELETE FROM nodes WHERE {where}", PATS)
        changed = True

    # drive-letter canon: promote lower-case-drive nodes, deleting any that collide with an upper twin
    nodes = con.execute("SELECT qualified_name, file_path FROM nodes").fetchall()
    have = {qn for qn, _ in nodes}
    deduped = 0
    for qn, fp in nodes:
        cq = canon(qn)
        if cq == qn:
            continue
        changed = True
        if cq in have:
            con.execute("DELETE FROM nodes WHERE qualified_name=?", (qn,))
            deduped += 1
        else:
            con.execute("UPDATE nodes SET qualified_name=?, file_path=? WHERE qualified_name=?", (cq, canon(fp), qn))
            have.add(cq)
    for col in ("source_qualified", "target_qualified", "file_path"):
        for (v,) in con.execute(f"SELECT DISTINCT {col} FROM edges").fetchall():
            if canon(v) != v:
                con.execute(f"UPDATE edges SET {col}=? WHERE {col}=?", (canon(v), v)); changed = True
    for (qn,) in con.execute("SELECT qualified_name FROM embeddings").fetchall():
        cq = canon(qn)
        if cq == qn:
            continue
        if con.execute("SELECT 1 FROM embeddings WHERE qualified_name=?", (cq,)).fetchone():
            con.execute("DELETE FROM embeddings WHERE qualified_name=?", (qn,))
        else:
            con.execute("UPDATE embeddings SET qualified_name=? WHERE qualified_name=?", (cq, qn))

    if changed:
        for stmt in (
            "DELETE FROM edges WHERE id NOT IN (SELECT MIN(id) FROM edges GROUP BY kind,source_qualified,target_qualified,file_path,line)",
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
        print(f"[crg-prune] {db}: removed {pruned} dependency nodes, deduped {deduped} case-duplicate nodes")
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
