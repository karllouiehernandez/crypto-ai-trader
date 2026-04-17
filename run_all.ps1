# Usage: .\run_all.ps1

$activateScript = 'D:\trader\Scripts\Activate.ps1'
$repoRoot = 'D:\trader\crypto_ai_trader'
$dashboardUrl = 'http://localhost:8501'

if (-not (Test-Path $activateScript)) {
    Write-Error "Virtual environment activation script not found: $activateScript"
    exit 1
}

if (-not (Test-Path $repoRoot)) {
    Write-Error "Repo root not found: $repoRoot"
    exit 1
}

$shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { 'pwsh' } else { 'powershell' }

$commonSetup = @(
    '$env:PYTHONUTF8 = ''1'''
    '$env:PYTHONIOENCODING = ''utf-8'''
    '[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()'
    '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()'
    'Set-Location ''D:\'''
    '. ''D:\trader\Scripts\Activate.ps1'''
    'Set-Location ''D:\trader\crypto_ai_trader'''
)

$traderCommand = ($commonSetup + @(
    'Write-Host ''Starting trader...'' -ForegroundColor Cyan'
    'python run_live.py'
)) -join '; '

$dashboardCommand = ($commonSetup + @(
    'Write-Host ''Starting dashboard...'' -ForegroundColor Cyan'
    'python -m streamlit run dashboard/streamlit_app.py'
)) -join '; '

Start-Process -FilePath $shell -ArgumentList @('-NoExit', '-Command', $traderCommand) -WorkingDirectory $repoRoot
Start-Process -FilePath $shell -ArgumentList @('-NoExit', '-Command', $dashboardCommand) -WorkingDirectory $repoRoot

Start-Sleep -Seconds 5
Start-Process $dashboardUrl

Write-Host 'Trader and dashboard launch commands were started.' -ForegroundColor Green
Write-Host "Dashboard: $dashboardUrl" -ForegroundColor Green
