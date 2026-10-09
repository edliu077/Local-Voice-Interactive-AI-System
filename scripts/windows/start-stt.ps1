#requires -Version 5.1
. (Join-Path $PSScriptRoot 'common.ps1')

$HostAddress = Get-LviaiLoopbackHost 'LVIAI_STT_HOST'
$Port = Get-LviaiPort 'LVIAI_STT_PORT' 8766
$Python = Require-LviaiFile (Get-LviaiPath 'LVIAI_STT_PYTHON' (Join-Path $script:LviaiProjectRoot 'backend\stt\.venv\Scripts\python.exe')) 'STT Python'
$Service = Require-LviaiFile (Join-Path $script:LviaiProjectRoot 'backend\stt\stt_service.py') 'STT service'
$ModelRoot = Require-LviaiDirectory (Get-LviaiPath 'LVIAI_STT_MODEL_ROOT' (Join-Path $script:LviaiProjectRoot 'models\faster-whisper')) 'Faster-Whisper model cache'
$Warmup = Require-LviaiFile (Get-LviaiPath 'LVIAI_STT_WARMUP_WAV' (Join-Path $script:LviaiProjectRoot 'assets\stt\warmup-16khz-mono.wav')) 'STT warm-up WAV'
$env:LVIAI_PROJECT_ROOT = $script:LviaiProjectRoot
$env:LVIAI_STT_MODEL_ROOT = $ModelRoot
$env:LVIAI_STT_WARMUP_WAV = $Warmup
$env:HF_HUB_OFFLINE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Deadline = [DateTime]::UtcNow.AddSeconds(120)
$Started = Start-LviaiLoggedProcess 'stt' $Python @($Service) (Split-Path -Parent $Service) $HostAddress $Port @($Service) 120
$Remaining = [Math]::Max(1, [int][Math]::Ceiling(($Deadline - [DateTime]::UtcNow).TotalSeconds))
Wait-LviaiJsonHealth 'stt' "http://${HostAddress}:$Port/health" 'ready' $Remaining $Started.Stdout $Started.Stderr
