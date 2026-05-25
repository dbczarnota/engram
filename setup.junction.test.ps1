#requires -Version 7
. "$PSScriptRoot\setup.lib.ps1"
$script:fails = 0
function Assert($cond, $msg) {
  if ($cond) { Write-Host "ok  : $msg" } else { Write-Host "FAIL: $msg"; $script:fails++ }
}

$root   = Join-Path ([IO.Path]::GetTempPath()) ("junc-" + [Guid]::NewGuid().ToString('N'))
$target = Join-Path $root 'target'
$other  = Join-Path $root 'other'
$link   = Join-Path $root 'link'
New-Item -ItemType Directory -Force $target | Out-Null
New-Item -ItemType Directory -Force $other  | Out-Null
try {
  Assert ((Get-JunctionState -Path $link -Target $target) -eq 'absent') "absent: nonexistent path"

  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  Assert ((Get-JunctionState -Path $link -Target $target) -eq 'ours') "ours: junction to target"
  Assert ((Get-JunctionState -Path $link -Target $other)  -eq 'other-junction') "other: junction elsewhere"

  $realDir = Join-Path $root 'real'
  New-Item -ItemType Directory -Force $realDir | Out-Null
  Assert ((Get-JunctionState -Path $realDir -Target $target) -eq 'real-dir') "real-dir: ordinary folder"
}
finally { Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue }

if ($script:fails -gt 0) { Write-Error "$script:fails assertion(s) failed"; exit 1 }
Write-Host "all passed"
