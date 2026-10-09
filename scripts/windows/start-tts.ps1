#requires -Version 5.1
. (Join-Path $PSScriptRoot 'common.ps1')

$HostAddress = Get-LviaiLoopbackHost 'LVIAI_TTS_HOST'
$Port = Get-LviaiPort 'LVIAI_TTS_PORT' 8765
$Python = Require-LviaiFile (Get-LviaiPath 'LVIAI_TTS_PYTHON' (Join-Path $script:LviaiProjectRoot 'backend\tts\.venv\Scripts\python.exe')) 'TTS Python'
$ServiceDir = Require-LviaiDirectory (Join-Path $script:LviaiProjectRoot 'backend\tts') 'TTS service directory'
$ModelRoot = Require-LviaiDirectory (Get-LviaiPath 'LVIAI_TTS_MODEL_ROOT' (Join-Path $script:LviaiProjectRoot 'models\qwen3-tts\0.6b-base')) 'Qwen3-TTS model'
$ReferenceAudio = Require-LviaiFile (Get-LviaiPath 'LVIAI_TTS_REFERENCE_AUDIO' (Join-Path $script:LviaiProjectRoot 'assets\voice\reference-short.wav')) 'private voice reference WAV'
$ReferenceText = Require-LviaiFile (Get-LviaiPath 'LVIAI_TTS_REFERENCE_TEXT' (Join-Path $script:LviaiProjectRoot 'assets\voice\reference-short.txt')) 'private voice reference transcript'
$ModelCache = Get-LviaiPath 'LVIAI_MODEL_ROOT' (Join-Path $script:LviaiProjectRoot 'models')
$env:LVIAI_PROJECT_ROOT = $script:LviaiProjectRoot
$env:LVIAI_TTS_MODEL_ROOT = $ModelRoot
$env:LVIAI_TTS_REFERENCE_AUDIO = $ReferenceAudio
$env:LVIAI_TTS_REFERENCE_TEXT = $ReferenceText
$env:HF_HOME = Join-Path $ModelCache 'qwen-hf-cache'
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:TRANSFORMERS_CACHE = Join-Path $env:HF_HOME 'transformers'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Deadline = [DateTime]::UtcNow.AddSeconds(120)
$Started = Start-LviaiLoggedProcess 'tts' $Python @('-m', 'uvicorn', 'tts_service:app', '--host', $HostAddress, '--port', "$Port", '--no-access-log') $ServiceDir $HostAddress $Port @('uvicorn', 'tts_service:app') 120
$Remaining = [Math]::Max(1, [int][Math]::Ceiling(($Deadline - [DateTime]::UtcNow).TotalSeconds))
Wait-LviaiJsonHealth 'tts' "http://${HostAddress}:$Port/health" 'ready' $Remaining $Started.Stdout $Started.Stderr
