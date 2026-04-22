@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM One-time Windows bootstrap for crypto_ai_trader.
REM Safe by design:
REM - does not overwrite .env
REM - does not delete or reset the DB
REM - does not change active artifact/runtime targets

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "VENV_DIR=%REPO_ROOT%\.venv"
set "REQ_FILE=%REPO_ROOT%\requirements.txt"
set "REQ_DEV_FILE=%REPO_ROOT%\requirements-dev.txt"
set "ENV_EXAMPLE=%REPO_ROOT%\.env.example"
set "ENV_FILE=%REPO_ROOT%\.env"
set "PYTHON_CMD="
set "PYTHON_ARGS="

echo === crypto_ai_trader one-time Windows installer ===
echo Repo root: %REPO_ROOT%
echo.

call :resolve_python
if errorlevel 1 goto :fail

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/6] Creating virtual environment...
    call "%PYTHON_CMD%" %PYTHON_ARGS% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        goto :fail
    )
) else (
    echo [1/6] Virtual environment already exists.
)

set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
set "PYTHON_ARGS="
set "PIP_EXE=%VENV_DIR%\Scripts\pip.exe"

echo [2/6] Upgrading pip...
call "%PYTHON_CMD%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [3/6] Installing runtime requirements...
"%PIP_EXE%" install -r "%REQ_FILE%"
if errorlevel 1 goto :fail

if exist "%REQ_DEV_FILE%" (
    echo [4/6] Installing dev requirements...
    "%PIP_EXE%" install -r "%REQ_DEV_FILE%"
    if errorlevel 1 goto :fail
) else (
    echo [4/6] No requirements-dev.txt found. Skipping dev extras.
)

if exist "%ENV_FILE%" (
    echo [5/6] .env already exists. Leaving it unchanged.
) else (
    if exist "%ENV_EXAMPLE%" (
        echo [5/6] Creating .env from .env.example...
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        if errorlevel 1 goto :fail
    ) else (
        echo [5/6] .env.example not found. Skipping .env creation.
    )
)

echo [6/6] Initializing database tables and Playwright browser support...
call "%PYTHON_CMD%" -c "from database.models import init_db; init_db(); print('Database initialized.')"
if errorlevel 1 goto :fail
call "%PYTHON_CMD%" -m playwright install chromium
if errorlevel 1 (
    echo Playwright browser install failed. You can retry later with:
    echo   .venv\Scripts\python.exe -m playwright install chromium
    goto :fail
)

echo.
echo Install complete.
echo.
echo Next steps:
echo   1. Edit credentials in .env if needed.
echo   2. Start the workbench/runtime with:
echo      run_all.ps1
echo   3. Or launch individual services with:
echo      .venv\Scripts\python.exe -m streamlit run dashboard\streamlit_app.py
echo      .venv\Scripts\python.exe run_live.py
echo.
exit /b 0

:resolve_python
if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_CMD=%VENV_DIR%\Scripts\python.exe"
    set "PYTHON_ARGS="
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3.10 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
        set "PYTHON_ARGS=-3.10"
        exit /b 0
    )
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=py"
        set "PYTHON_ARGS=-3"
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    set "PYTHON_ARGS="
    exit /b 0
)

echo Could not find Python 3. Install Python 3.10+ first, then re-run this script.
exit /b 1

:fail
echo.
echo Installer failed. No cleanup was performed.
exit /b 1
