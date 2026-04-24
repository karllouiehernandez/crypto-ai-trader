@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "TARGET_ROOT=%~1"
set "BUNDLE_DIR="

if /I "%~1"=="/?" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help

if "%TARGET_ROOT%"=="" (
    set /P TARGET_ROOT=Enter flash drive root or target folder ^(example E:\^): 
)

if "%TARGET_ROOT%"=="" goto :fail
if not exist "%TARGET_ROOT%" (
    echo Target path does not exist: %TARGET_ROOT%
    goto :fail
)

set "BUNDLE_DIR=%TARGET_ROOT%\crypto_ai_trader_bundle"

echo === crypto_ai_trader flash-drive bundle ===
echo Source repo : %REPO_ROOT%
echo Target bundle: %BUNDLE_DIR%
echo.

if not exist "%BUNDLE_DIR%" mkdir "%BUNDLE_DIR%"

echo [1/2] Mirroring repo into bundle folder...
robocopy "%REPO_ROOT%" "%BUNDLE_DIR%" /MIR ^
    /XD ".git" ".venv" "backups" "reports" "__pycache__" ".pytest_cache" ".mypy_cache" ".ruff_cache" ^
    /XF ".env" "app.db" "crypto_trader.db" "knowledge\\experiment_log.md" ".run_live_eval.err" ".run_live_eval.out" ".streamlit_eval.err" ".streamlit_eval.out" ".streamlit_eval_phase2.err" ".streamlit_eval_phase2.out" ".streamlit_eval_phase47.err" ".streamlit_eval_phase47.out" ".streamlit_headed.err" ".streamlit_headed.out" ".streamlit_phase1.err" ".streamlit_phase1.out" "*.pyc" "*.pyo" "*.db-shm" "*.db-wal"
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
    echo Robocopy failed with code %RC%.
    goto :fail
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$items = @('.streamlit_headed.err','.streamlit_headed.out','.streamlit_phase1.err','.streamlit_phase1.out','.streamlit_eval.err','.streamlit_eval.out','.streamlit_eval_phase2.err','.streamlit_eval_phase2.out','.streamlit_eval_phase47.err','.streamlit_eval_phase47.out','app.db','crypto_trader.db');" ^
    "$items | ForEach-Object { $path = Join-Path '%BUNDLE_DIR%' $_; if (Test-Path $path) { Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue } }" >nul 2>nul

echo [2/2] Bundle ready.
echo.
echo Next steps on Windows:
echo   1. Safely eject the flash drive.
echo   2. Insert it into the Jetson Nano.
echo.
echo Next steps on Jetson:
echo   1. Mount the drive and locate crypto_ai_trader_bundle
echo   2. Run:
echo      bash /media/$USER/^<your_usb^>/crypto_ai_trader_bundle/deployment/install_from_bundle.sh /media/$USER/^<your_usb^>/crypto_ai_trader_bundle
echo   3. Edit ~/crypto_ai_trader/.env
echo   4. Start the service:
echo      sudo systemctl start crypto-trader
echo.
exit /b 0

:help
echo Usage:
echo   prepare_jetson_flash_drive.bat [FLASH_DRIVE_ROOT]
echo.
echo Example:
echo   prepare_jetson_flash_drive.bat E:\
echo.
echo This creates or refreshes:
echo   FLASH_DRIVE_ROOT\crypto_ai_trader_bundle
echo.
echo It excludes local runtime artifacts, .env, local DB placeholders, .venv, reports, backups, and experiment logs.
exit /b 0

:fail
echo.
echo Flash-drive bundle creation failed. No cleanup was performed.
exit /b 1
