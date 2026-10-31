param([ValidateSet('preflight','start','status','stop')][string]$Action='preflight')
. (Join-Path $PSScriptRoot 'livetalking-env.ps1')
& (Join-Path $LtRoot '.venv-livetalking\Scripts\python.exe') -B -s (Join-Path $PSScriptRoot 'ws-service.py') $Action
if($LASTEXITCODE -ne 0){throw "WS manager failed: $LASTEXITCODE"}
