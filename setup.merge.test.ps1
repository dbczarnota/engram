#requires -Version 7
. "$PSScriptRoot\setup.lib.ps1"
$script:fails = 0
function Assert($cond, $msg) {
  if ($cond) { Write-Host "ok  : $msg" } else { Write-Host "FAIL: $msg"; $script:fails++ }
}

$cmd = 'pwsh -NoProfile -File "C:\v\hooks\capture.ps1"'

# adds to empty settings
$r = Merge-SessionEndHook -Settings @{} -Command $cmd
Assert ($r.Changed -eq $true) "empty: reports changed"
Assert ($r.Settings['hooks']['SessionEnd'].Count -eq 1) "empty: one SessionEnd entry"
Assert ($r.Settings['hooks']['SessionEnd'][0]['hooks'][0]['command'] -eq $cmd) "empty: command stored"

# idempotent: re-merging the same command does not duplicate
$r2 = Merge-SessionEndHook -Settings $r.Settings -Command $cmd
Assert ($r2.Changed -eq $false) "idempotent: reports unchanged"
Assert ($r2.Settings['hooks']['SessionEnd'].Count -eq 1) "idempotent: still one entry"

# preserves an unrelated existing hook
$existing = @{ hooks = @{ SessionEnd = @( @{ hooks = @( @{ type='command'; command='other.ps1' } ) } ) } }
$r3 = Merge-SessionEndHook -Settings $existing -Command $cmd
Assert ($r3.Changed -eq $true) "preserve: reports changed"
Assert ($r3.Settings['hooks']['SessionEnd'].Count -eq 2) "preserve: keeps existing + adds ours"

if ($script:fails -gt 0) { Write-Error "$script:fails assertion(s) failed"; exit 1 }
Write-Host "all passed"
