param([ValidateSet('preflight','start','stop','status')][string]$Action='preflight')
$ErrorActionPreference='Stop'
$TtsRoot=Split-Path $PSScriptRoot -Parent
$env:PYTHONDONTWRITEBYTECODE='1';$env:PYTHONNOUSERSITE='1';$env:PYTHONUTF8='1';$env:PYTHONIOENCODING='utf-8';$env:PYTHONPATH=$TtsRoot
$env:HF_HUB_OFFLINE='1';$env:TRANSFORMERS_OFFLINE='1';$env:PIP_CACHE_DIR=Join-Path $TtsRoot 'cache\tts\pip'
$TtsCaches=@{HF_HOME='cache\hf';HUGGINGFACE_HUB_CACHE='cache\hf\hub';HF_HUB_CACHE='cache\hf\hub';TRANSFORMERS_CACHE='cache\hf\transformers';TORCH_HOME='cache\torch';XDG_CACHE_HOME='cache';CUDA_CACHE_PATH='cache\cuda';TORCHINDUCTOR_CACHE_DIR='cache\torchinductor';TRITON_CACHE_DIR='cache\triton';NUMBA_CACHE_DIR='cache\numba'}
foreach($TtsName in $TtsCaches.Keys){$TtsPath=Join-Path $TtsRoot $TtsCaches[$TtsName];[IO.Directory]::CreateDirectory($TtsPath)|Out-Null;[Environment]::SetEnvironmentVariable($TtsName,$TtsPath,'Process')}
$env:TEMP=Join-Path $TtsRoot 'runtime\tmp';$env:TMP=$env:TEMP
[IO.Directory]::CreateDirectory($env:TEMP)|Out-Null
& (Join-Path $TtsRoot '.venv-tts\Scripts\python.exe') -B -s (Join-Path $PSScriptRoot 'tts-service.py') $Action
if($LASTEXITCODE -ne 0){throw "TTS manager failed: $LASTEXITCODE"}
