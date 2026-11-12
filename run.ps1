$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $python = 'python'
}

Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
        Push-Location 'frontend'
        try {
            if (-not (Test-Path -LiteralPath 'node_modules')) {
                npm.cmd ci
                if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
            }
            npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally {
            Pop-Location
        }
    }

    Write-Host 'Open http://127.0.0.1:8000 after Uvicorn starts.'
    & $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
