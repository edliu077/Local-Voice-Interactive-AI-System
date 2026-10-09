#requires -Version 5.1
. (Join-Path $PSScriptRoot 'common.ps1')

$HostAddress = Get-LviaiLoopbackHost 'LVIAI_WS_HOST'
$Port = Get-LviaiPort 'LVIAI_WS_PORT' 8767
$Python = Require-LviaiFile (Get-LviaiPath 'LVIAI_ORCHESTRATOR_PYTHON' (Join-Path $script:LviaiProjectRoot 'backend\orchestrator\.venv\Scripts\python.exe')) 'orchestrator Python'
$Server = Require-LviaiFile (Join-Path $script:LviaiProjectRoot 'backend\orchestrator\voice_ws_server.py') 'WebSocket server'
$VadRoot = Require-LviaiDirectory (Get-LviaiPath 'LVIAI_VAD_MODEL_ROOT' (Join-Path $script:LviaiProjectRoot 'models\silero-vad')) 'Silero VAD cache'
$env:LVIAI_PROJECT_ROOT = $script:LviaiProjectRoot
$env:LVIAI_VAD_MODEL_ROOT = $VadRoot
$env:LVIAI_PLAYBACK_MODE = 'browser'
$env:TORCH_HOME = $VadRoot
$env:HF_HUB_OFFLINE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Started = Start-LviaiLoggedProcess 'websocket' $Python @($Server, '--host', $HostAddress, '--port', "$Port") (Split-Path -Parent $Server) $HostAddress $Port @($Server) 120
Write-Host "WebSocket ready at ws://${HostAddress}:$Port (PID $($Started.ProcessId))."
