$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Python venv not found: $Python" }

$oldUrl = $env:SATNO_CRM_LEAD_URL
$oldToken = $env:SATNO_BALE_MARKET_INGEST_TOKEN
$token = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
$env:SATNO_BALE_MARKET_INGEST_TOKEN = $token
$env:SATNO_CRM_LEAD_URL = "http://127.0.0.1:8099/functions/v1/ingest_leads"

$receiver = Start-Process -FilePath $Python -ArgumentList "tools\mock_crm_receiver.py" -WorkingDirectory $Root -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 2
    Push-Location $Root
    try {
        & $Python "tools\crm_adapter_acceptance.py"
        if ($LASTEXITCODE -ne 0) { throw "CRM adapter acceptance failed" }
    }
    finally { Pop-Location }
}
finally {
    if ($receiver -and -not $receiver.HasExited) { Stop-Process -Id $receiver.Id -Force }
    $env:SATNO_CRM_LEAD_URL = $oldUrl
    $env:SATNO_BALE_MARKET_INGEST_TOKEN = $oldToken
}
