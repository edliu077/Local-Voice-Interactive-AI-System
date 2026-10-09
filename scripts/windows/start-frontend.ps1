#requires -Version 5.1
. (Join-Path $PSScriptRoot 'common.ps1')

$HostAddress = Get-LviaiLoopbackHost 'LVIAI_FRONTEND_HOST'
$Port = Get-LviaiPort 'LVIAI_FRONTEND_PORT' 3000
$Frontend = Require-LviaiDirectory (Join-Path $script:LviaiProjectRoot 'frontend') 'frontend directory'
$NextCli = Require-LviaiFile (Join-Path $Frontend 'node_modules\next\dist\bin\next') 'Next.js CLI'
$BuildId = Require-LviaiFile (Join-Path $Frontend '.next\BUILD_ID') 'production BUILD_ID; run build-frontend.ps1 first'
$NodeSetting = [Environment]::GetEnvironmentVariable('LVIAI_NODE_EXE', 'Process')
if ([string]::IsNullOrWhiteSpace($NodeSetting)) {
    $NodeCommand = Get-Command node.exe -ErrorAction Stop
    $Node = $NodeCommand.Source
} else {
    $Node = Require-LviaiFile (Get-LviaiPath 'LVIAI_NODE_EXE' $NodeSetting) 'Node.js executable'
}

$env:LVIAI_PROJECT_ROOT = $script:LviaiProjectRoot
$env:NODE_ENV = 'production'
$Started = Start-LviaiLoggedProcess 'frontend' $Node @($NextCli, 'start', '--hostname', $HostAddress, '--port', "$Port") $Frontend $HostAddress $Port @($NextCli, 'start') 60
$ReadyUrl = "http://${HostAddress}:$Port/"
Wait-LviaiHttpOk 'frontend' $ReadyUrl 60 $Started.Stdout $Started.Stderr
$LongRunningProcess = Get-Process -Id $Started.ProcessId -ErrorAction Stop
Write-Host "Frontend production server ready at $ReadyUrl"
Write-Host "PID=$($Started.ProcessId); working_set_bytes=$($LongRunningProcess.WorkingSet64); BUILD_ID=$((Get-Content -LiteralPath $BuildId -Raw).Trim())"
Write-Host "Logs: $($Started.Stdout) and $($Started.Stderr)"
