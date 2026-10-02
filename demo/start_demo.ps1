param(
    [switch]$SkipInstall,
    [switch]$SkipTraining
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$NodeModules = Join-Path $ProjectRoot 'frontend\node_modules'
$RuntimeDir = Join-Path $PSScriptRoot '.runtime'

function Test-PortFree([int]$Port) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -eq $listener
}

function Wait-ForHttp([string]$Url, [int]$Seconds = 45) {
    $until = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $until) {
        try { Invoke-RestMethod -Uri $Url -TimeoutSec 2 | Out-Null; return $true } catch { Start-Sleep -Milliseconds 500 }
    }
    return $false
}

Push-Location $ProjectRoot
try {
    if (-not (Test-PortFree 8000) -or -not (Test-PortFree 5173)) {
        throw 'Ports 8000 or 5173 are already in use. Stop the existing FlowFreeze services or choose different ports before starting this demo.'
    }
    if (-not (Test-Path $Python)) {
        $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($pyLauncher) { & $pyLauncher.Source -3.11 -m venv .venv }
        else { python -m venv .venv }
    }
    if (-not (Test-Path $Python)) { throw 'Could not create .venv. Install Python 3.11+ and try again.' }

    if (-not $SkipInstall) {
        & $Python -c "import fastapi, pandas, sklearn, networkx" 2>$null
        if ($LASTEXITCODE -ne 0) { & $Python -m pip install -r requirements.txt }
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
        if (-not (Test-Path $NodeModules)) {
            $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
            if (-not $npm) { throw 'npm was not found. Install Node.js 20+ and try again.' }
            & $npm.Source ci --prefix frontend
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
    }

    $requiredData = @('transactions.csv','wallets.csv','incidents.csv','ground_truth.csv','flowfreeze.db')
    $missingData = $requiredData | Where-Object { -not (Test-Path (Join-Path $ProjectRoot "data\$_")) }
    if ($missingData) {
        & $Python -m data_generator.generate --seed 42
        if ($LASTEXITCODE -ne 0) { throw 'Synthetic data generation failed.' }
    }
    if (-not $SkipTraining -and (-not (Test-Path (Join-Path $ProjectRoot 'ml\artifacts\fraud_model.joblib')) -or -not (Test-Path (Join-Path $ProjectRoot 'ml\artifacts\next_move_model.joblib')))) {
        & $Python -m ml.train --seed 42
        if ($LASTEXITCODE -ne 0) { throw 'Model training failed.' }
    }

    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    $apiOut = Join-Path $RuntimeDir 'api.stdout.log'
    $apiErr = Join-Path $RuntimeDir 'api.stderr.log'
    $webOut = Join-Path $RuntimeDir 'frontend.stdout.log'
    $webErr = Join-Path $RuntimeDir 'frontend.stderr.log'
    $pythonProcess = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $vite = Join-Path $NodeModules 'vite\bin\vite.js'
    $webProcess = Start-Process -FilePath $node -ArgumentList @($vite,'--host','127.0.0.1','--port','5173') -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -PassThru -WindowStyle Hidden -RedirectStandardOutput $webOut -RedirectStandardError $webErr
    $record = @{ apiPid = $pythonProcess.Id; frontendPid = $webProcess.Id; startedAt = (Get-Date).ToString('o') }
    [IO.File]::WriteAllText((Join-Path $RuntimeDir 'processes.json'), ($record | ConvertTo-Json), [Text.UTF8Encoding]::new($false))

    if (-not (Wait-ForHttp 'http://127.0.0.1:8000/health')) {
        throw "API did not become ready. See $apiErr"
    }
    if (-not (Wait-ForHttp 'http://127.0.0.1:5173')) {
        throw "Frontend did not become ready. See $webErr"
    }
    Write-Host 'FlowFreeze is ready.' -ForegroundColor Green
    Write-Host 'Frontend: http://127.0.0.1:5173'
    Write-Host 'API docs: http://127.0.0.1:8000/docs'
    Write-Host 'Stop services: .\demo\stop_demo.ps1'
    Write-Host "Logs: $RuntimeDir"
} catch {
    if ($pythonProcess -and -not $pythonProcess.HasExited) { Stop-Process -Id $pythonProcess.Id -Force -ErrorAction SilentlyContinue }
    if ($webProcess -and -not $webProcess.HasExited) { Stop-Process -Id $webProcess.Id -Force -ErrorAction SilentlyContinue }
    Write-Error $_
    exit 1
} finally {
    Pop-Location
}
