$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Python venv not found: $Python" }

Push-Location $Root
try {
    Write-Host "SATNO CRM adapter acceptance (in-process mock receiver)" -ForegroundColor Cyan

    & $Python -m unittest tests.test_crm_mock_receiver -v
    if ($LASTEXITCODE -ne 0) {
        throw "CRM adapter acceptance failed"
    }

    Write-Host "PASS: CRM adapter acceptance completed." -ForegroundColor Green
    Write-Host "No real CRM endpoint or production token was used." -ForegroundColor DarkGray
}
finally {
    Pop-Location
}
