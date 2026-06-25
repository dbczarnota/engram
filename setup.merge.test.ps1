#requires -Version 7
. "$PSScriptRoot\setup.lib.ps1"
$script:fails = 0
function Assert($cond, $msg) {
  if ($cond) { Write-Host "ok  : $msg" } else { Write-Host "FAIL: $msg"; $script:fails++ }
}

$cmd = 'pwsh -NoProfile -File "C:\v\hooks\capture.ps1"'

# adds to empty settings
$r = Merge-Hook -Settings @{} -EventName 'SessionEnd' -Command $cmd
Assert ($r.Changed -eq $true) "empty: reports changed"
Assert ($r.Settings['hooks']['SessionEnd'].Count -eq 1) "empty: one SessionEnd entry"
Assert ($r.Settings['hooks']['SessionEnd'][0]['hooks'][0]['command'] -eq $cmd) "empty: command stored"

# idempotent: re-merging the same command does not duplicate
$r2 = Merge-Hook -Settings $r.Settings -EventName 'SessionEnd' -Command $cmd
Assert ($r2.Changed -eq $false) "idempotent: reports unchanged"
Assert ($r2.Settings['hooks']['SessionEnd'].Count -eq 1) "idempotent: still one entry"

# preserves an unrelated existing hook
$existing = @{ hooks = @{ SessionEnd = @( @{ hooks = @( @{ type='command'; command='other.ps1' } ) } ) } }
$r3 = Merge-Hook -Settings $existing -EventName 'SessionEnd' -Command $cmd
Assert ($r3.Changed -eq $true) "preserve: reports changed"
Assert ($r3.Settings['hooks']['SessionEnd'].Count -eq 2) "preserve: keeps existing + adds ours"

# generic over event name: a second event is independent
$u = Merge-Hook -Settings $r3.Settings -EventName 'UserPromptSubmit' -Command 'auto.ps1'
Assert ($u.Changed -eq $true) "event: adds UserPromptSubmit"
Assert ($u.Settings['hooks']['UserPromptSubmit'].Count -eq 1) "event: one UserPromptSubmit entry"
Assert ($u.Settings['hooks']['SessionEnd'].Count -eq 2) "event: SessionEnd untouched"

# matcher: a tool-scoped hook stores its matcher alongside the command
$pt = Merge-Hook -Settings @{} -EventName 'PostToolUse' -Command 'track.ps1' -Matcher 'Edit|Write|MultiEdit'
Assert ($pt.Changed -eq $true) "matcher: adds PostToolUse"
Assert ($pt.Settings['hooks']['PostToolUse'][0]['matcher'] -eq 'Edit|Write|MultiEdit') "matcher: matcher stored"
Assert ($pt.Settings['hooks']['PostToolUse'][0]['hooks'][0]['command'] -eq 'track.ps1') "matcher: command stored"
$pt2 = Merge-Hook -Settings $pt.Settings -EventName 'PostToolUse' -Command 'track.ps1' -Matcher 'Edit|Write|MultiEdit'
Assert ($pt2.Changed -eq $false) "matcher: idempotent on same command"

# lifecycle hook (no matcher) omits the matcher key
$lc = Merge-Hook -Settings @{} -EventName 'Stop' -Command 'stop.ps1'
Assert (-not $lc.Settings['hooks']['Stop'][0].ContainsKey('matcher')) "no-matcher: matcher key absent"

# autoMemoryEnabled: set when absent
$a = Set-AutoMemoryDisabled -Settings @{}
Assert ($a.Changed -eq $true) "automem: changed when absent"
Assert ($a.Settings['autoMemoryEnabled'] -eq $false) "automem: set to false"

# autoMemoryEnabled: idempotent when already false
$a2 = Set-AutoMemoryDisabled -Settings $a.Settings
Assert ($a2.Changed -eq $false) "automem: unchanged when already false"

# autoMemoryEnabled: flips an existing true
$a3 = Set-AutoMemoryDisabled -Settings @{ autoMemoryEnabled = $true }
Assert ($a3.Changed -eq $true) "automem: flips true to false"
Assert ($a3.Settings['autoMemoryEnabled'] -eq $false) "automem: now false"

if ($script:fails -gt 0) { Write-Error "$script:fails assertion(s) failed"; exit 1 }
Write-Host "all passed"
