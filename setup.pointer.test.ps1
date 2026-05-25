#requires -Version 7
. "$PSScriptRoot\setup.lib.ps1"
$script:fails = 0
function Assert($cond, $msg) {
  if ($cond) { Write-Host "ok  : $msg" } else { Write-Host "FAIL: $msg"; $script:fails++ }
}

$start = '<!-- brain-vault-pointer:start -->'

# insert into empty
$r = Update-ClaudePointer -Text '' -Block 'BLOCK-V1'
Assert ($r.Changed -eq $true) "insert: changed"
Assert ($r.Text -match [regex]::Escape($start)) "insert: has start marker"
Assert ($r.Text -match 'BLOCK-V1') "insert: has block"

# preserve surrounding content + append once
$existing = "# My global config`n`nsome rules`n"
$r2 = Update-ClaudePointer -Text $existing -Block 'BLOCK-V1'
Assert ($r2.Text -match 'some rules') "append: preserves existing text"
Assert (([regex]::Matches($r2.Text, [regex]::Escape($start))).Count -eq 1) "append: exactly one start marker"

# replace between markers (new content)
$r3 = Update-ClaudePointer -Text $r2.Text -Block 'BLOCK-V2'
Assert ($r3.Text -match 'BLOCK-V2') "replace: has new block"
Assert ($r3.Text -notmatch 'BLOCK-V1') "replace: old block gone"
Assert (([regex]::Matches($r3.Text, [regex]::Escape($start))).Count -eq 1) "replace: still one marker"
Assert ($r3.Text -match 'some rules') "replace: still preserves existing text"

# truly idempotent: same block -> no change
$r4 = Update-ClaudePointer -Text $r3.Text -Block 'BLOCK-V2'
Assert ($r4.Changed -eq $false) "idempotent: unchanged when block identical"

if ($script:fails -gt 0) { Write-Error "$script:fails assertion(s) failed"; exit 1 }
Write-Host "all passed"
