#requires -Version 7
Set-StrictMode -Version Latest

function Merge-SessionEndHook {
  param([hashtable]$Settings, [Parameter(Mandatory)][string]$Command)
  if ($null -eq $Settings) { $Settings = @{} }
  if (-not $Settings.ContainsKey('hooks'))               { $Settings['hooks'] = @{} }
  if (-not $Settings['hooks'].ContainsKey('SessionEnd')) { $Settings['hooks']['SessionEnd'] = @() }

  foreach ($entry in @($Settings['hooks']['SessionEnd'])) {
    if ($entry -is [hashtable] -and $entry.ContainsKey('hooks')) {
      foreach ($h in @($entry['hooks'])) {
        if ($h -is [hashtable] -and $h['command'] -eq $Command) {
          return @{ Settings = $Settings; Changed = $false }
        }
      }
    }
  }

  $newEntry = @{ hooks = @( @{ type = 'command'; command = $Command } ) }
  $Settings['hooks']['SessionEnd'] = @($Settings['hooks']['SessionEnd']) + $newEntry
  return @{ Settings = $Settings; Changed = $true }
}
