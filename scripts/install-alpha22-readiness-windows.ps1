param(
    [string]$Root = "C:\Satno\SatnoBaleMarket-v05",
    [string]$Branch = "feature/staff-v05"
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
$env:PATH = (Split-Path $Git -Parent) + ";" + $env:PATH
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Python venv not found: $Python" }
if (-not (Test-Path (Join-Path $Root ".git"))) { throw "Root is not a Git checkout: $Root" }

Push-Location $Root
try {
    $dirty = & $Git status --porcelain
    if ($dirty) { throw "Working tree is not clean. Stop and review local changes first." }

    # Alpha 2.1 must not receive live connector traffic.
    $crmReady = & $Python -c "from dotenv import dotenv_values; v=dotenv_values('.env.local'); print('1' if (v.get('SATNO_CRM_LEAD_URL') or '').strip() else '0')"
    if ($crmReady.Trim() -eq "1") { throw "SATNO_CRM_LEAD_URL is already configured. Clear it before Alpha 2.2 readiness install." }

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backup = "C:\Satno\backup\bale-market-alpha22-$stamp"
    New-Item -ItemType Directory -Force $backup | Out-Null

    $previousHead = (& $Git rev-parse HEAD).Trim()
    Set-Content (Join-Path $backup "PREVIOUS_HEAD.txt") $previousHead -Encoding ASCII
    Set-Content (Join-Path $backup "BRANCH.txt") ((& $Git branch --show-current).Trim()) -Encoding UTF8

    $db = Join-Path $Root "satno_market.db"
    if (-not (Test-Path $db)) { throw "Database not found: $db" }
    $dbBackup = Join-Path $backup "satno_market.db"
    & $Python -c "import sqlite3; s=sqlite3.connect(r'$db'); d=sqlite3.connect(r'$dbBackup'); s.backup(d); d.close(); s.close(); print('DB BACKUP OK')"
    if ($LASTEXITCODE -ne 0) { throw "SQLite backup failed" }

    if (Test-Path ".env.local") { Copy-Item ".env.local" (Join-Path $backup ".env.local") -Force }

    & $Git fetch origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
    & $Git checkout $Branch
    if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
    & $Git pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only failed" }

    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency install failed" }

    & $Python -c "from db import init_db; init_db(); print('SCHEMA OK')"
    if ($LASTEXITCODE -ne 0) { throw "Schema migration failed" }

    & ".\scripts\test-v05-windows.ps1"
    if ($LASTEXITCODE -ne 0) { throw "Regression validation failed" }

    & ".\scripts\test-crm-adapter-windows.ps1"
    if ($LASTEXITCODE -ne 0) { throw "CRM mock acceptance failed" }

    # Restart only Bale Market tasks; do not touch Farsicom, VoIP, or other services.
    foreach ($name in @("SATNO-BaleMarket-v05-Web","SATNO-BaleMarket-v05-Sync")) {
        if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
            Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 2
    if (Get-ScheduledTask -TaskName "SATNO-BaleMarket-v05-Web" -ErrorAction SilentlyContinue) {
        Start-ScheduledTask -TaskName "SATNO-BaleMarket-v05-Web"
        Start-Sleep -Seconds 5
    }

    $health = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 10
    if ($health.status -ne "ok" -or $health.version -ne "0.5.0") {
        throw "Bale Market health check failed after install"
    }

    Write-Host "INSTALL PASS" -ForegroundColor Green
    Write-Host "Backup path: $backup" -ForegroundColor Yellow
    Write-Host "CRM live delivery remains disabled until Alpha 2.2."
}
finally {
    Pop-Location
}
