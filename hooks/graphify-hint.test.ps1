# hooks/graphify-hint.test.ps1 — PreToolUse semantics
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("braingfx_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
Set-Content (Join-Path $brain "_meta\engram.json") -Value '{ "graphify": { "enabled": true, "hint": { "enabled": true } } }' -Encoding utf8
$bin = Join-Path $brain "bin"; New-Item -ItemType Directory -Force $bin | Out-Null
"@echo off`r`necho graphify-stub" | Set-Content "$bin\graphify.cmd" -Encoding ascii
$repo = Join-Path $brain "repo"; New-Item -ItemType Directory -Force (Join-Path $repo "graphify-out") | Out-Null
Set-Content (Join-Path $repo "graphify-out\graph.json") -Value '{}' -Encoding utf8
Set-Content (Join-Path $repo "graphify-out\GRAPH_REPORT.md") -Value "# Graph Report`n- Built from commit: ``deadbeef``" -Encoding utf8
$env:BRAIN_HOME = $brain
$env:PATH = "$bin;$env:PATH"
$script = Join-Path $here "graphify-hint.ps1"
function Run($tool, $sid, $cwd) {
  $payload = @{ tool_name = $tool; tool_input = @{ pattern = "foo" }; cwd = $cwd; session_id = $sid } | ConvertTo-Json -Compress
  return ($payload | pwsh -NoProfile -File $script 2>&1) -join "`n"
}
function Get-ScratchPath($sid) { Join-Path $brain "_meta\state\scratch-$sid.json" }
try {
  # (a) Grep in a repo with a graph -> hint
  $a = Run "Grep" "s1" $repo
  if ($a -notmatch "graphify query") { throw "FAIL(a): expected hint, got: $a" }
  if ($a -notmatch "additionalContext") { throw "FAIL(a): not hook JSON: $a" }
  if ($a -notmatch "Code graph available for this repo") { throw "FAIL(a): missing health-check marker: $a" }

  # (b) second call same session inside cooldown -> silent
  $b = Run "Glob" "s1" $repo
  if ($b.Trim()) { throw "FAIL(b): expected cooldown silence, got: $b" }

  # (c) cooldown expired -> fires again (backdate the scratch timestamp)
  $sp = Get-ChildItem (Join-Path $brain "_meta\state") -Filter "*.json" | Where-Object { $_.Name -match "s1" } | Select-Object -First 1
  $sc = Get-Content $sp.FullName -Raw | ConvertFrom-Json
  $sc.gfxHintedAt = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 600
  $sc | ConvertTo-Json -Depth 6 | Set-Content $sp.FullName -Encoding utf8
  $c = Run "Grep" "s1" $repo
  if ($c -notmatch "graphify query") { throw "FAIL(c): expected re-hint after cooldown, got: $c" }

  # (d) no graph.json -> silent
  $repo2 = Join-Path $brain "repo2"; New-Item -ItemType Directory -Force (Join-Path $repo2 "graphify-out") | Out-Null
  $d = Run "Grep" "s2" $repo2
  if ($d.Trim()) { throw "FAIL(d): expected silence (no graph.json), got: $d" }

  # (e) stale: cwd is a git repo whose HEAD != GRAPH_REPORT commit
  $gitrepo = Join-Path $brain "gitrepo"; New-Item -ItemType Directory -Force (Join-Path $gitrepo "graphify-out") | Out-Null
  Set-Content (Join-Path $gitrepo "graphify-out\graph.json") -Value '{}' -Encoding utf8
  Set-Content (Join-Path $gitrepo "graphify-out\GRAPH_REPORT.md") -Value "Built from commit: ``deadbeef``" -Encoding utf8
  & git -C $gitrepo init -q 2>$null
  Set-Content (Join-Path $gitrepo "x.txt") "hi" -Encoding ascii
  & git -C $gitrepo add -A 2>$null
  & git -C $gitrepo -c user.email=a@b.c -c user.name=t commit -qm init 2>$null
  $e = Run "Grep" "s3" $gitrepo
  if ($e -notmatch "stale") { throw "FAIL(e): expected stale flag, got: $e" }

  # (f) toggle off -> silent
  Set-Content (Join-Path $brain "_meta\engram.json") -Value '{ "graphify": { "hint": { "enabled": false } } }' -Encoding utf8
  $f = Run "Grep" "s4" $repo
  if ($f.Trim()) { throw "FAIL(f): expected silence (toggle off), got: $f" }

  "PASS: graphify-hint fires on search tools, honors cooldown + toggle, flags stale, silent without a graph"
}
finally {
  Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item Env:BRAIN_HOME -ErrorAction SilentlyContinue
}
