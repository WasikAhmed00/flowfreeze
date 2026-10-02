$ErrorActionPreference = 'Stop'
$RuntimeDir = Join-Path $PSScriptRoot '.runtime'
$ProcessFile = Join-Path $RuntimeDir 'processes.json'
if (-not (Test-Path $ProcessFile)) {
    Write-Host 'No FlowFreeze demo process record found.'
    exit 0
}

$record = Get-Content $ProcessFile -Raw | ConvertFrom-Json
$targets = @(
    @{ Id = [int]$record.apiPid; Match = 'uvicorn' },
    @{ Id = [int]$record.frontendPid; Match = 'vite\bin\vite.js' }
)
foreach ($target in $targets) {
    try {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($target.Id)"
    } catch {
        throw "Could not verify process $($target.Id); run this script in a PowerShell session with permission to inspect local process command lines. The PID record was kept."
    }
    if (-not $processInfo) { continue }
    if ($processInfo.CommandLine -notmatch [regex]::Escape($target.Match)) {
        throw "Refusing to stop process $($target.Id) because its command line does not match FlowFreeze. The PID record was kept."
    }
    Stop-Process -Id $target.Id -Force
    Write-Host "Stopped FlowFreeze process $($target.Id)."
}
Remove-Item -LiteralPath $ProcessFile -Force
