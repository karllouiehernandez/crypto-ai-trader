# Usage:
#   .\run_all.ps1
#   .\run_all.ps1 -InstallDeps
#   .\run_all.ps1 -WithMcpServer
#
# Starts the dashboard and paper trader in separate PowerShell windows.

[CmdletBinding()]
param(
    [switch]$InstallDeps,
    [switch]$WithMcpServer,
    [switch]$SkipBrowser
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$dashboardUrl = "http://localhost:8501"
$mcpUrl = "http://localhost:8765/sse"

function Resolve-PythonPath {
    param([string]$Root)

    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $Root "venv\Scripts\python.exe"),
        "D:\trader\Scripts\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Could not find a Python executable. Create a virtualenv or install Python first."
}

function Assert-EnvFile {
    param([string]$Root)

    $envPath = Join-Path $Root ".env"
    if (-not (Test-Path $envPath)) {
        throw "Missing .env at $envPath. Copy .env.example to .env and fill in your credentials first."
    }
}

function Test-PackageImport {
    param(
        [string]$PythonExe,
        [string]$ModuleName
    )

    $result = & $PythonExe -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)"
    return ($LASTEXITCODE -eq 0)
}

function Install-Requirements {
    param(
        [string]$PythonExe,
        [string]$Root
    )

    Write-Host "Installing requirements..." -ForegroundColor Cyan
    & $PythonExe -m pip install -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency install failed."
    }
}

function New-ProcessCommand {
    param(
        [string]$Root,
        [string]$PythonExe,
        [string]$Title,
        [string]$Command
    )

    $escapedRoot = $Root.Replace("'", "''")
    $escapedPython = $PythonExe.Replace("'", "''")
    $escapedTitle = $Title.Replace("'", "''")

    return @(
        "`$host.UI.RawUI.WindowTitle = '$escapedTitle'"
        "Set-Location '$escapedRoot'"
        "`$env:PYTHONUTF8 = '1'"
        "`$env:PYTHONIOENCODING = 'utf-8'"
        "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()"
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()"
        "& '$escapedPython' $Command"
    ) -join "; "
}

if (-not (Test-Path $repoRoot)) {
    throw "Repo root not found: $repoRoot"
}

Assert-EnvFile -Root $repoRoot
$pythonExe = Resolve-PythonPath -Root $repoRoot

if ($InstallDeps -or -not (Test-PackageImport -PythonExe $pythonExe -ModuleName "streamlit")) {
    Install-Requirements -PythonExe $pythonExe -Root $repoRoot
}

$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

$dashboardCommand = New-ProcessCommand `
    -Root $repoRoot `
    -PythonExe $pythonExe `
    -Title "crypto_ai_trader - dashboard" `
    -Command "-m streamlit run dashboard/streamlit_app.py"

$traderCommand = New-ProcessCommand `
    -Root $repoRoot `
    -PythonExe $pythonExe `
    -Title "crypto_ai_trader - trader" `
    -Command "run_live.py"

Start-Process -FilePath $shell -ArgumentList @("-NoExit", "-Command", $traderCommand) -WorkingDirectory $repoRoot | Out-Null
Start-Process -FilePath $shell -ArgumentList @("-NoExit", "-Command", $dashboardCommand) -WorkingDirectory $repoRoot | Out-Null

if ($WithMcpServer) {
    $mcpCommand = New-ProcessCommand `
        -Root $repoRoot `
        -PythonExe $pythonExe `
        -Title "crypto_ai_trader - mcp" `
        -Command "run_mcp_server.py"
    Start-Process -FilePath $shell -ArgumentList @("-NoExit", "-Command", $mcpCommand) -WorkingDirectory $repoRoot | Out-Null
}

Start-Sleep -Seconds 5
if (-not $SkipBrowser) {
    Start-Process $dashboardUrl | Out-Null
}

Write-Host "Launched trader and dashboard." -ForegroundColor Green
Write-Host "Repo: $repoRoot" -ForegroundColor Green
Write-Host "Python: $pythonExe" -ForegroundColor Green
Write-Host "Dashboard: $dashboardUrl" -ForegroundColor Green
if ($WithMcpServer) {
    Write-Host "MCP: $mcpUrl" -ForegroundColor Green
}
