# Turing Machine Simulator & Halting Predictor Launcher
# Runs directly from inside the TuringMachine repository root.
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$yashrajPart = Join-Path $repoRoot "Yashraj Part"
$frontendDir = Join-Path $yashrajPart "frontend"
$frontendDist = Join-Path $frontendDir "dist"
$nodeModules = Join-Path $frontendDir "node_modules"

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TURING MACHINE SIMULATOR & BOUNDED HALTING PREDICTOR     " -ForegroundColor Yellow
Write-Host "===========================================================" -ForegroundColor Cyan

# 1. Install frontend dependencies if missing
if (-not (Test-Path $nodeModules)) {
    Write-Host "[*] Installing frontend dependencies (npm install)..." -ForegroundColor Cyan
    Push-Location $frontendDir
    try {
        npm install
    } finally {
        Pop-Location
    }
}

# 2. Build frontend production distribution if missing
if (-not (Test-Path (Join-Path $frontendDist "index.html"))) {
    Write-Host "[*] Building frontend production bundle (npm run build)..." -ForegroundColor Cyan
    Push-Location $frontendDir
    try {
        npm run build
    } finally {
        Pop-Location
    }
}

# 3. Configure Python environment & launch FastAPI
Push-Location $yashrajPart
try {
    $env:PYTHONPATH = $yashrajPart
    Write-Host "[+] Serving application at http://localhost:8000" -ForegroundColor Green
    Write-Host "    Press Ctrl+C to stop the server." -ForegroundColor Gray

    # Launch browser after server starts
    Start-Process "http://localhost:8000"

    python -m uvicorn backend.app.main:app --port 8000 --reload
} finally {
    Pop-Location
}

