#requires -Version 5.1
. (Join-Path $PSScriptRoot 'common.ps1')

$Frontend = Require-LviaiDirectory (Join-Path $script:LviaiProjectRoot 'frontend') 'frontend directory'
$NextCli = Require-LviaiFile (Join-Path $Frontend 'node_modules\next\dist\bin\next') 'Next.js CLI'
$NodeSetting = [Environment]::GetEnvironmentVariable('LVIAI_NODE_EXE', 'Process')
if ([string]::IsNullOrWhiteSpace($NodeSetting)) {
    $NodeCommand = Get-Command node.exe -ErrorAction Stop
    $Node = $NodeCommand.Source
} else {
    $Node = Require-LviaiFile (Get-LviaiPath 'LVIAI_NODE_EXE' $NodeSetting) 'Node.js executable'
}

$RuntimeRoot = Get-LviaiPath 'LVIAI_RUNTIME_ROOT' (Join-Path $script:LviaiProjectRoot 'runtime')
$LogDir = Join-Path $RuntimeRoot 'logs'
$Stdout = Join-Path $LogDir 'frontend-build-stdout.txt'
$Stderr = Join-Path $LogDir 'frontend-build-stderr.txt'
$BuildId = Join-Path $Frontend '.next\BUILD_ID'
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

$env:LVIAI_PROJECT_ROOT = $script:LviaiProjectRoot
$env:NODE_ENV = 'production'
$Process = Start-Process -FilePath $Node -ArgumentList @($NextCli, 'build', '--webpack') -WorkingDirectory $Frontend -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -Wait -PassThru
if ($Process.ExitCode -ne 0) {
    throw "Frontend production build failed with exit code $($Process.ExitCode). See $Stdout and $Stderr"
}
if (-not (Test-Path -LiteralPath $BuildId -PathType Leaf)) {
    throw "Frontend build exited successfully but BUILD_ID is missing: $BuildId"
}
Write-Host "Frontend production build complete (Webpack). BUILD_ID=$((Get-Content -LiteralPath $BuildId -Raw).Trim())"
Write-Host "Build logs: $Stdout and $Stderr"
