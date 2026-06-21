#requires -Version 7
# PreToolUse hook (matcher: Grep|Glob): code-graph grep-assist.
# When the repo has a CRG graph (.code-review-graph/graph.db), look up the SYMBOL terms in the grep
# pattern via CRG's nodes table (exact name match — precise, no FTS false positives) and INJECT the
# answer (name/kind/file:line) inline, so the agent gets the graph answer instead of re-deriving it
# from raw grep. Handles multi-symbol OR-patterns. Terms that are not symbols (status strings, regex,
# keywords) simply don't match → omitted, and a pure string/content grep injects nothing (grep is right
# there). Only speaks when CRG has a concrete answer; otherwise silent.
# NEVER denies the grep (fail-open): any miss/error exits 0 and the grep proceeds normally.
$ErrorActionPreference = "Stop"
try {
  if ($env:BRAIN_CAPTURE_ACTIVE) { exit 0 }
  $raw = [Console]::In.ReadToEnd()
  if (-not $raw) { exit 0 }
  $hook = $raw | ConvertFrom-Json
  $cwd = "" + $hook.cwd
  $pattern = "" + $hook.tool_input.pattern
  if (-not $cwd -or -not $pattern) { exit 0 }

  # A pattern with >=3 alternatives (>=2 unescaped '|') is a CONCEPT search, not a symbol lookup —
  # exact-name matching returns noise or one lucky hit there. Stay silent; grep is the right tool.
  # (Single symbol or A|B 2-term lookups still get the hint.)
  $pipes = ([regex]::Matches($pattern, '(?<!\\)\|')).Count
  if ($pipes -ge 2) { exit 0 }

  $brain = if ($env:BRAIN_HOME) { $env:BRAIN_HOME } else { "<BRAIN_PATH>" }
  $cfgPath = "$brain\_meta\engram.json"
  if (Test-Path $cfgPath) {
    try { $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
          if ($cfg.graphify -and $cfg.graphify.hint -and $cfg.graphify.hint.enabled -eq $false) { exit 0 } } catch {}
  }

  $db = Join-Path $cwd ".code-review-graph\graph.db"
  $msg = $null

  # PRIMARY: CRG exact-name lookup of the pattern's symbol terms → inject the actual answer.
  if (Test-Path $db) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { $py = (Get-Command python3 -ErrorAction SilentlyContinue).Source }
    if ($py) {
      $script = @'
import sqlite3, sys, os, re
db, pattern = sys.argv[1], sys.argv[2]
repo = os.path.dirname(os.path.dirname(db))
STOP = {"async","await","def","class","return","self","import","from","true","false","none",
        "and","not","for","while","router","url","base","status","public","with","the","def_"}
# Never surface dependency / build-artifact code — those names (Stream, Source, ...) collide with
# app concepts and drown the real hit. Skip a row whose path has any of these segments.
IGNORE_SEG = {"node_modules","dist","build",".venv","venv","__pycache__",".next","target",
              "vendor","coverage",".cache",".git","site-packages",".tox","out"}
def is_app(path):
    if not path: return True
    parts = re.split(r"[\\/]", path)
    return not any(p in IGNORE_SEG for p in parts)
terms = [t for t in dict.fromkeys(re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", pattern))
         if t.lower() not in STOP]
if not terms:
    sys.exit(0)
con = sqlite3.connect(db)
seen, out = set(), []
for t in terms[:10]:
    # pull a few candidates and keep the first that lives in app code (filter happens here, not in
    # SQL, so a name that exists ONLY in node_modules yields nothing rather than a misleading hit).
    rows = con.execute(
        "SELECT name,kind,file_path,line_start FROM nodes WHERE name = ? COLLATE NOCASE "
        "ORDER BY (kind='Class') DESC, length(file_path) LIMIT 8", (t,)).fetchall()
    for n, k, f, l in rows:
        if not is_app(f): continue
        key = (n, f, l)
        if key in seen: continue
        seen.add(key)
        rel = os.path.relpath(f, repo) if f else f
        out.append(f"{n} ({k}) {rel}:{l}")
        break
for line in out:
    print(line)
'@
      $tmp = [IO.Path]::Combine([IO.Path]::GetTempPath(), "crg_lookup_$PID.py")
      [IO.File]::WriteAllText($tmp, $script, [Text.UTF8Encoding]::new($false))
      try { $found = (& $py $tmp $db $pattern 2>$null) } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
      $found = @($found | Where-Object { $_ })
      if ($found.Count -gt 0) {
        $body = ($found -join "`n  ")
        $msg = "[CRG] Code graph already locates these symbols - use this instead of grepping for them:`n  $body`nFor callers / blast-radius use the ``code-review-graph`` MCP tools (query_graph / get_impact_radius). Keep grep for string/content/status search the graph doesn't index."
      }
    }
  }

  # Only speak when CRG has a concrete answer. A string/content grep with no symbol hit gets
  # silence (grep is the right tool there) — avoids passive-hint noise.
  if (-not $msg) { exit 0 }
  $payload = @{ hookSpecificOutput = @{ hookEventName = "PreToolUse"; additionalContext = $msg } }
  [Console]::OutputEncoding = [Text.Encoding]::UTF8
  $payload | ConvertTo-Json -Depth 6 -Compress
  exit 0
} catch { exit 0 }
