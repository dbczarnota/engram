#requires -Version 7
Set-StrictMode -Version Latest

function Merge-Hook {
  param(
    [hashtable]$Settings,
    [Parameter(Mandatory)][string]$EventName,
    [Parameter(Mandatory)][string]$Command
  )
  if ($null -eq $Settings) { $Settings = @{} }
  if (-not $Settings.ContainsKey('hooks'))             { $Settings['hooks'] = @{} }
  if (-not $Settings['hooks'].ContainsKey($EventName)) { $Settings['hooks'][$EventName] = @() }

  foreach ($entry in @($Settings['hooks'][$EventName])) {
    if ($entry -is [hashtable] -and $entry.ContainsKey('hooks')) {
      foreach ($h in @($entry['hooks'])) {
        if ($h -is [hashtable] -and $h['command'] -eq $Command) {
          return @{ Settings = $Settings; Changed = $false }
        }
      }
    }
  }

  $newEntry = @{ hooks = @( @{ type = 'command'; command = $Command } ) }
  $Settings['hooks'][$EventName] = @($Settings['hooks'][$EventName]) + $newEntry
  return @{ Settings = $Settings; Changed = $true }
}

function Set-AutoMemoryDisabled {
  param([hashtable]$Settings)
  if ($null -eq $Settings) { $Settings = @{} }
  if ($Settings.ContainsKey('autoMemoryEnabled') -and $Settings['autoMemoryEnabled'] -eq $false) {
    return @{ Settings = $Settings; Changed = $false }
  }
  $Settings['autoMemoryEnabled'] = $false
  return @{ Settings = $Settings; Changed = $true }
}

function Update-ClaudePointer {
  param([string]$Text, [Parameter(Mandatory)][string]$Block)
  if ($null -eq $Text) { $Text = '' }
  $start   = '<!-- brain-vault-pointer:start -->'
  $end     = '<!-- brain-vault-pointer:end -->'
  $wrapped = "$start`n$Block`n$end"

  $pattern = [regex]::Escape($start) + '.*?' + [regex]::Escape($end)
  $rx      = [regex]::new($pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
  if ($rx.IsMatch($Text)) {
    $new = $rx.Replace($Text, { param($m) $wrapped }, 1)
    return @{ Text = $new; Changed = ($new -ne $Text) }
  }
  $prefix = if ($Text.TrimEnd().Length -gt 0) { $Text.TrimEnd() + "`n`n" } else { '' }
  $new = $prefix + $wrapped + "`n"
  return @{ Text = $new; Changed = $true }
}

function Get-JunctionState {
  param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Target)
  if (-not (Test-Path $Path)) { return 'absent' }
  $item = Get-Item -LiteralPath $Path -Force
  if ($item.LinkType -in @('Junction', 'SymbolicLink')) {
    $linkTarget = @($item.Target)[0]
    $a = (Resolve-Path -LiteralPath $linkTarget -ErrorAction SilentlyContinue)
    $b = (Resolve-Path -LiteralPath $Target     -ErrorAction SilentlyContinue)
    if ($a -and $b -and $a.Path.TrimEnd('\') -eq $b.Path.TrimEnd('\')) { return 'ours' }
    return 'other-junction'
  }
  return 'real-dir'
}
