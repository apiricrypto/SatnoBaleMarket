# Configure a repeated one-time trigger. Does not enable the task or run Sync.
param(
    [ValidateRange(15, 1440)]
    [int]$Minutes = 60,
    [string]$TaskName = 'SATNO-BaleMarket-v05-Sync'
)
$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if ($task.State -eq 'Running') {
    throw 'Sync is running; wait for it to finish.'
}
# Save the original task XML before making any changes.
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupDir = Join-Path $env:ProgramData 'Satno\BaleMarket\TaskBackups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$backupPath = Join-Path $backupDir "$($TaskName)-$stamp.xml"
Export-ScheduledTask -TaskName $TaskName -ErrorAction Stop |
    Set-Content -LiteralPath $backupPath -Encoding UTF8

# The -Daily trigger does not expose a writable Repetition property on
# Windows PowerShell 5.1. A -Once trigger supports native repetition params.
# Ten-year horizon is explicit and avoids undocumented infinite-duration hacks.
$start = (Get-Date).AddMinutes(5)
$trigger = New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutes) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$wasDisabled = $task.State -eq 'Disabled'
Set-ScheduledTask -TaskName $TaskName -Trigger $trigger -ErrorAction Stop | Out-Null
if ($wasDisabled) {
    Disable-ScheduledTask -TaskName $TaskName -ErrorAction Stop | Out-Null
}
$after = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
$actual = $after.Triggers[0].Repetition.Interval
$expected = [System.Xml.XmlConvert]::ToString([TimeSpan]::FromMinutes($Minutes))
if ($actual -ne $expected -or ($wasDisabled -and $after.State -ne 'Disabled')) {
    throw "Verification failed. Task XML backup: $backupPath"
}
Write-Host "SYNC INTERVAL UPDATED: $Minutes minutes"
Write-Host "SYNC TASK STATE: $($after.State)"
Write-Host "BACKUP: $backupPath"
Write-Host 'The task was not enabled automatically.'
