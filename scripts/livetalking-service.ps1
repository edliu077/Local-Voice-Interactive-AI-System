param([ValidateSet('preflight','start','stop','status')][string]$Action='preflight')
. (Join-Path $PSScriptRoot 'livetalking-env.ps1')
$env:LIVETALKING_LOG=Join-Path $LtRoot 'runtime\livetalking\livetalking-current.log'
[IO.Directory]::CreateDirectory((Split-Path $env:LIVETALKING_LOG -Parent)) | Out-Null
& (Join-Path $LtRoot '.venv-livetalking\Scripts\python.exe') -B -s (Join-Path $PSScriptRoot 'livetalking-service.py') $Action
if($LASTEXITCODE -ne 0){throw "LiveTalking manager failed: $LASTEXITCODE"}
