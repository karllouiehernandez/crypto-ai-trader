# Usage: . .\start_trader.ps1

$activateScript = 'D:\trader\Scripts\Activate.ps1'
$repoRoot = 'D:\trader\crypto_ai_trader'

Set-Location 'D:\'

if (-not (Test-Path $activateScript)) {
    Write-Error "Virtual environment activation script not found: $activateScript"
    return
}

. $activateScript
Set-Location $repoRoot
