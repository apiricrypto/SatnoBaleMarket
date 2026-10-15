# Update only the Bale Market Sync task cadence. Does not enable the task.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/configure_sync_interval.ps1 -Minutes 60
param(
    [ValidateRange(15, 1440)]
    [int]$Minutes = 60,
    [string]$TaskName = 'SATNO-BaleMarket-v05-Sync'
)

$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if ($task.State -eq 'Running') {
    throw 'Sync is still running. Do not change the trigger during a live run.'
}
# Task Scheduler uses one day repeated triggers; preserve task action,
# credentials, principal and settings. Only the trigger is replaced.
$trigger = New-ScheduledTaskTrigger -Daily -At '00:00'
$trigger.Repetition.Interval = [System.Xml.XmlConvert]::ToString([TimeSpan]::FromMinutes($Minutes))
$trigger.Repetition.Duration = 'P1D'
$trigger.Repetition.StopAtDurationEnd = $false
Set-ScheduledTask -TaskName $TaskName -Trigger $trigger -ErrorAction Stop | Out-Null
$after = Get-ScheduledTask -TaskName $TaskName
if ($after.Triggers[0].Repetition.Interval -ne $trigger.Repetition.Interval) {
    throw 'Trigger verification failed'
}
Write-Host "SYNC INTERVAL UPDATED: $Minutes minutes"
Write-Host "SYNC TASK STATE: $($after.State)"
Write-Host 'NOT enabled automatically; keep Disabled until live acceptance passes.'
