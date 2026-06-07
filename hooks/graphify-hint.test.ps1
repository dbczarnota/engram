# hooks/graphify-hint.test.ps1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$brain = Join-Path ([IO.Path]::GetTempPath()) ("braingfx_" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force (Join-Path $brain "_meta\state") | Out-Null
Set-Content (Join-Path $brain "_meta\engram.json") -Value '{ "graphify": { "enabled": true, "hint": { "enabled": true } } }' -Encoding utf8
$bin = Join-Path $brain "bin"; New-Item -ItemType Directory -Force $bin | Out-Null
"@echo off`r`necho graphify-stub" | Set-Content "$bin\graphify.cmd" -Encoding ascii
$repo = Join-Path $brain "repo"; New-Item -ItemType Directory -Force (Join-Path $repo "graphify-out") | Out-Null
Set-Content (Join-Path $repo "graphify-out\GRAPH_REPORT.md") -Value "# Graph Report`n- Built from commit: ``deadbeef``" -Encoding utf8
$env:BRAIN_HOME = $brain
$env:PATH = "$bin;$env:PATH"
$script = Join-Path $here "graphify-hint.ps1"
function Run($prompt, $sid, $cwd) {
  $payload = @{ prompt = $prompt; cwd = $cwd; session_id = $sid } | ConvertTo-Json -Compress
  return ($payload | pwsh -NoProfile -File $script 2>&1) -join "`n"
}
try {
  # (a) structural prompt + graph present -> hint
  $a = Run "what depends on the AuthModule?" "s1" $repo
  if ($a -notmatch "graphify query") { throw "FAIL(a): expected hint, got: $a" }
  if ($a -notmatch "additionalContext") { throw "FAIL(a): not hook JSON: $a" }

  # (b) ordinary prompt -> silent
  $b = Run "please rename this variable" "s2" $repo
  if ($b.Trim()) { throw "FAIL(b): expected silence, got: $b" }

  # (c) no graphify-out -> silent
  $repo2 = Join-Path $brain "repo2"; New-Item -ItemType Directory -Force $repo2 | Out-Null
  $c = Run "what calls foo?" "s3" $repo2
  if ($c.Trim()) { throw "FAIL(c): expected silence (no graph), got: $c" }

  # (d) second call same session -> dedup silent
  $d = Run "what imports the database layer?" "s1" $repo
  if ($d.Trim()) { throw "FAIL(d): expected dedup silence, got: $d" }

  # (e) stale: cwd is a git repo whose HEAD != GRAPH_REPORT commit
  $gitrepo = Join-Path $brain "gitrepo"; New-Item -ItemType Directory -Force (Join-Path $gitrepo "graphify-out") | Out-Null
  Set-Content (Join-Path $gitrepo "graphify-out\GRAPH_REPORT.md") -Value "Built from commit: ``deadbeef``" -Encoding utf8
  & git -C $gitrepo init -q 2>$null
  Set-Content (Join-Path $gitrepo "x.txt") "hi" -Encoding ascii
  & git -C $gitrepo add -A 2>$null
  & git -C $gitrepo -c user.email=a@b.c -c user.name=t commit -qm init 2>$null
  $e = Run "architecture overview?" "s5" $gitrepo
  if ($e -notmatch "stale") { throw "FAIL(e): expected stale flag, got: $e" }

  "PASS: graphify-hint fires on structural prompts, dedups, flags stale, stays silent otherwise"
}
finally {
  Remove-Item $brain -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item Env:BRAIN_HOME -ErrorAction SilentlyContinue
}
