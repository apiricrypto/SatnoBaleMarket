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
    if ($LASTEXITCODE -ne 0) {
        throw "Compile failed with exit code $LASTEXITCODE"
    }

    Write-Host "[2/4] Unit/regression tests"
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Unit/regression tests failed with exit code $LASTEXITCODE"
    }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        foreach ($candidate in @(
            "C:\Program Files\Git\cmd\git.exe",
            "C:\Program Files\Git\bin\git.exe",
            "C:\Program Files (x86)\Git\cmd\git.exe"
        )) {
            if (Test-Path $candidate) { $git = Get-Item $candidate; break }
        }
    }
    if (-not $git) { throw "Git executable not found for repository guards" }
    $gitExe = $git.Source
    if (-not $gitExe) { $gitExe = $git.FullName }

    Write-Host "[3/4] Secret/file guard"
    $blocked = @(".env.local", "satno_market.db")
    foreach ($item in $blocked) {
        $tracked = & $gitExe ls-files -- $item 2>$null
        if ($tracked) {
            throw "Sensitive runtime file is tracked by git: $item"
        }
    }

    Write-Host "[4/4] Branch guard"
    $branch = (& $gitExe branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to determine git branch"
    }
    if ($branch -ne "feature/staff-v05") {
        throw "Expected feature/staff-v05, got: $branch"
    }

    Write-Host "PASS: v0.5 code/tests/guards completed." -ForegroundColor Green
}
finally {
    Pop-Location
}
