$ErrorActionPreference = "Stop"

Write-Host "SATNO Bale Market v0.5 validation" -ForegroundColor Cyan

$python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$python = [System.IO.Path]::GetFullPath($python)

if (-not (Test-Path $python)) {
    throw "Python venv not found: $python"
}

Push-Location (Join-Path $PSScriptRoot "..")
try {
    Write-Host "[1/4] Compile"
    & $python -m compileall -q .

    Write-Host "[2/4] Unit/regression tests"
    & $python -m unittest discover -s tests -v

    Write-Host "[3/4] Secret/file guard"
    $blocked = @(".env.local", "satno_market.db")
    foreach ($item in $blocked) {
        $tracked = git ls-files --error-unmatch $item 2>$null
        if ($LASTEXITCODE -eq 0) {
            throw "Sensitive runtime file is tracked by git: $item"
        }
    }

    Write-Host "[4/4] Branch guard"
    $branch = (git branch --show-current).Trim()
    if ($branch -ne "feature/staff-v05") {
        throw "Expected feature/staff-v05, got: $branch"
    }

    Write-Host "PASS: v0.5 code/tests/guards completed." -ForegroundColor Green
}
finally {
    Pop-Location
}
