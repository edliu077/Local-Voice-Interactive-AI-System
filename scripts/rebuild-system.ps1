param([ValidateSet('preflight','start','status','stop')][string]$Action='preflight')
. (Join-Path $PSScriptRoot 'livetalking-env.ps1')
& (Join-Path $LtRoot '.venv-livetalking\Scripts\python.exe') -B -s (Join-Path $PSScriptRoot 'rebuild-system.py') $Action
if($LASTEXITCODE -ne 0){throw "Unified manager blocked or failed: $LASTEXITCODE. See runtime\stack\runs; no success is implied."}
