# Local development only. Does not deploy, start Sync, or change scheduled tasks.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (!(Test-Path '.venv/Scripts/python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment' }
    }
    $pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
    & $pythonExe -m pip install -r requirements.txt httpx==0.28.1
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & $pythonExe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed' }
    New-Item -ItemType Directory -Force '.localdev' | Out-Null
    $env:DATABASE_PATH = Join-Path $projectRoot '.localdev/market.db'
    $env:SATNO_CRM_LEAD_URL = ''
    $env:SESSION_COOKIE_SECURE = '0'
    $userCount = & $pythonExe -c "from db import init_db,connect; init_db(); con=connect(); print(con.execute('SELECT COUNT(*) FROM staff_users').fetchone()[0]); con.close()"
    if ($LASTEXITCODE -ne 0) { throw 'Local database initialization failed' }
    if ([int]$userCount -eq 0) {
        & $pythonExe create_staff_user.py admin --role admin --name 'Local SATNO Admin'
        if ($LASTEXITCODE -ne 0) { throw 'Admin creation failed' }
    }
    & $pythonExe -m uvicorn main:app --host 127.0.0.1 --port 8005
    if ($LASTEXITCODE -ne 0) { throw 'Local server failed' }
}
finally { Pop-Location }
