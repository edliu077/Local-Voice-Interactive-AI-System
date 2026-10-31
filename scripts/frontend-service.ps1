param([ValidateSet('preflight','start','status','stop')][string]$Action='preflight',[ValidateSet('production','development')][string]$Mode='production')
. (Join-Path $PSScriptRoot 'livetalking-env.ps1')
$env:NODE_OPTIONS='--max-old-space-size=1024';$env:NODE_PATH=$null;$env:NEXT_TELEMETRY_DISABLED='1'
$env:REBUILD_FRONTEND_MODE=$Mode
& (Join-Path $LtRoot '.venv-livetalking\Scripts\python.exe') -B -s (Join-Path $PSScriptRoot 'frontend-service.py') $Action
if($LASTEXITCODE -ne 0){throw "Frontend manager failed: $LASTEXITCODE"}
