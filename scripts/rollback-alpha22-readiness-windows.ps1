param(
    [Parameter(Mandatory=$true)][string]$BackupPath,
    [string]$Root = "C:\Satno\SatnoBaleMarket-v05"
)
$ErrorActionPreference = "Stop"

function Find-Git {
    $cmd = Get-Command git -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @(
        "C:\Program Files\Git\cmd\git.exe",
        "C:\Program Files\Git\bin\git.exe",
        "C:\Program Files (x86)\Git\cmd\git.exe"
    )) { if (Test-Path $p) { return $p } }
    throw "Git executable not found."
}

$Git = Find-Git
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$headFile = Join-Path $BackupPath "PREVIOUS_HEAD.txt"
$dbBackup = Join-Path $BackupPath "satno_market.db"
if (-not (Test-Path $headFile)) { throw "PREVIOUS_HEAD.txt not found in backup" }
if (-not (Test-Path $dbBackup)) { throw "Database backup not found" }
$previousHead = (Get-Content $headFile -Raw).Trim()

foreach ($name in @("SATNO-BaleMarket-v05-Web","SATNO-BaleMarket-v05-Sync")) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

Push-Location $Root
try {
    & $Git checkout --detach $previousHead
    if ($LASTEXITCODE -ne 0) { throw "Could not restore previous code HEAD" }
    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Could not restore dependencies" }

    Copy-Item $dbBackup (Join-Path $Root "satno_market.db") -Force
    $envBackup = Join-Path $BackupPath ".env.local"
    if (Test-Path $envBackup) { Copy-Item $envBackup (Join-Path $Root ".env.local") -Force }

    if (Get-ScheduledTask -TaskName "SATNO-BaleMarket-v05-Web" -ErrorAction SilentlyContinue) {
        Start-ScheduledTask -TaskName "SATNO-BaleMarket-v05-Web"
        Start-Sleep -Seconds 5
    }
    $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 10
    Write-Host ("ROLLBACK PASS: " + ($health | ConvertTo-Json -Compress)) -ForegroundColor Green
    Write-Host "Only SATNO Bale Market files/tasks were changed."
}
finally {
    Pop-Location
}
