@echo off
title Turing Machine Simulator ^& Predictor Server
cd /d "%~dp0"

echo ===================================================
echo   Starting Turing Machine Simulator ^& Predictor
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe!
    echo Please make sure the virtual environment exists in this directory.
    echo.
    pause
    exit /b 1
)

echo [1/2] Opening web application in default browser...
start http://127.0.0.1:8000

echo [2/2] Launching backend server on http://127.0.0.1:8000 ...
echo Press Ctrl+C anytime to stop the server.
echo.

".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Server terminated with error code %ERRORLEVEL%.
    pause
)
