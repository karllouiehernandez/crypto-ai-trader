@echo off
setlocal EnableExtensions EnableDelayedExpansion

if /I "%~1"=="/?" goto :help
if /I "%~1"=="-h" goto :help
if /I "%~1"=="--help" goto :help

set "JETSON_HOST=%~1"
set "JETSON_USER=%~2"
set "JETSON_PORT=%~3"
set "SCRIPT_DIR=%~dp0deployment"
set "REMOTE_SCRIPT=%SCRIPT_DIR%\setup_remote_access.sh"
set "SSH_DIR=%USERPROFILE%\.ssh"
set "SSH_KEY=%SSH_DIR%\id_ed25519"
set "SSH_PUB=%SSH_KEY%.pub"
set "SSH_PORT_FLAG="

if "%JETSON_HOST%"=="" set /P JETSON_HOST=Jetson host or IP: 
if "%JETSON_USER%"=="" set /P JETSON_USER=Jetson username: 
if "%JETSON_PORT%"=="" set "JETSON_PORT=22"

if "%JETSON_HOST%"=="" goto :fail
if "%JETSON_USER%"=="" goto :fail
if not exist "%REMOTE_SCRIPT%" (
    echo Missing helper script: %REMOTE_SCRIPT%
    goto :fail
)

where ssh >nul 2>nul || (echo ssh.exe not found. Install Windows OpenSSH client first.& goto :fail)
where scp >nul 2>nul || (echo scp.exe not found. Install Windows OpenSSH client first.& goto :fail)
where ssh-keygen >nul 2>nul || (echo ssh-keygen.exe not found. Install Windows OpenSSH client first.& goto :fail)

if not exist "%SSH_DIR%" mkdir "%SSH_DIR%"
if not exist "%SSH_PUB%" (
    echo No SSH key found. Creating one at %SSH_KEY% ...
    ssh-keygen -t ed25519 -f "%SSH_KEY%" -N ""
    if errorlevel 1 goto :fail
)

set "SSH_PORT_FLAG=-P %JETSON_PORT%"

echo === Jetson Nano one-time remote access setup ===
echo Host : %JETSON_HOST%
echo User : %JETSON_USER%
echo Port : %JETSON_PORT%
echo.
echo You may be prompted for the Jetson password and sudo password during setup.
echo.

echo [1/4] Copying Jetson-side setup helper...
scp %SSH_PORT_FLAG% "%REMOTE_SCRIPT%" %JETSON_USER%@%JETSON_HOST%:/tmp/setup_remote_access.sh
if errorlevel 1 goto :fail

echo [2/4] Enabling SSH server and SFTP support on Jetson...
ssh -p %JETSON_PORT% -t %JETSON_USER%@%JETSON_HOST% "bash /tmp/setup_remote_access.sh"
if errorlevel 1 goto :fail

echo [3/4] Installing your public key for passwordless access...
type "%SSH_PUB%" | ssh -p %JETSON_PORT% %JETSON_USER%@%JETSON_HOST% "umask 077; mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && cat >> ~/.ssh/authorized_keys"
if errorlevel 1 goto :fail

echo [4/4] Verifying passwordless SSH...
ssh -o BatchMode=yes -o ConnectTimeout=10 -p %JETSON_PORT% %JETSON_USER%@%JETSON_HOST% "echo SSH ready on $(hostname)"
if errorlevel 1 (
    echo Passwordless verification failed. SSH server may still be available, but the key setup needs review.
    goto :fail
)

echo.
echo Remote access is ready.
echo.
echo SSH:
echo   ssh -p %JETSON_PORT% %JETSON_USER%@%JETSON_HOST%
echo.
echo SFTP:
echo   sftp -P %JETSON_PORT% %JETSON_USER%@%JETSON_HOST%
echo.
echo Example deploy follow-up:
echo   1. Run prepare_jetson_flash_drive.bat E:\
echo   2. Move the flash drive to the Jetson
echo   3. Run deployment/install_from_bundle.sh from the mounted bundle
echo.
exit /b 0

:help
echo Usage:
echo   setup_jetson_remote_access.bat [JETSON_HOST] [JETSON_USER] [JETSON_PORT]
echo.
echo Example:
echo   setup_jetson_remote_access.bat 192.168.1.50 jetson 22
echo.
echo What it does:
echo   - creates a local ed25519 SSH key if missing
echo   - copies a helper script to the Jetson
echo   - installs/enables openssh-server on the Jetson
echo   - enables SFTP via the standard SSH server
echo   - appends your public key to ~/.ssh/authorized_keys
echo   - verifies passwordless SSH access
exit /b 0

:fail
echo.
echo Jetson remote-access setup failed. No cleanup was performed.
exit /b 1
