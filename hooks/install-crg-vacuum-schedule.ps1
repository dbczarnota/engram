#requires -Version 7
# Register a weekly Windows scheduled task that runs hooks/crg_maintenance.py — prune + VACUUM every
# registered CRG graph.db to reclaim free pages the per-commit prune leaves behind (VACUUM is too slow
# to run per-commit). See lessons/code-review-graph.md.
#
# Usage:  . hooks/install-crg-vacuum-schedule.ps1; Install-CrgVacuumSchedule
#         (optional) Install-CrgVacuumSchedule -DayOfWeek Sunday -At 3:30am -TaskName 'CRG Weekly Vacuum'

function Install-CrgVacuumSchedule {
  param(
    [string]$ScriptPath = (Join-Path $PSScriptRoot 'crg_maintenance.py'),
    [ValidateSet('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')]
    [string]$DayOfWeek = 'Sunday',
    [datetime]$At = '3:30am',
    [string]$TaskName = 'CRG Weekly Vacuum'
  )
  if (-not (Test-Path $ScriptPath)) { throw "script not found: $ScriptPath" }
  $py = (Get-Command python -ErrorAction SilentlyContinue).Source
  if (-not $py) { throw "python not on PATH — cannot schedule crg_maintenance.py" }

  $log = Join-Path $HOME '.cache\crg-vacuum.log'
  New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
  # Wrap in pwsh so we can redirect all streams to the log (scheduled-task actions can't redirect).
  $inner  = "& `"$py`" `"$ScriptPath`" *>> `"$log`""
  $action = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument "-NoProfile -NonInteractive -Command `"$inner`""
  $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $At
  # Catch up if the machine was off at the trigger time; don't fight battery/idle (best-effort maintenance).
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Weekly prune + VACUUM of all CRG graph.db files (reclaims free pages). Runs $ScriptPath." | Out-Null
  return $TaskName
}
