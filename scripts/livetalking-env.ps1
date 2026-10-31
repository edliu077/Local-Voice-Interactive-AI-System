$ErrorActionPreference='Stop'
$LtRoot=Split-Path $PSScriptRoot -Parent
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONNOUSERSITE='1'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH=Join-Path $LtRoot 'third_party\LiveTalking'
$LtDirs=@{TEMP='runtime\tmp';TMP='runtime\tmp';PIP_CACHE_DIR='cache\livetalking\pip';TORCH_HOME='cache\livetalking\torch';HF_HOME='cache\livetalking\hf';XDG_CACHE_HOME='cache\livetalking';NUMBA_CACHE_DIR='cache\livetalking\numba';CUDA_CACHE_PATH='cache\livetalking\cuda';MPLCONFIGDIR='cache\livetalking\matplotlib';TORCHINDUCTOR_CACHE_DIR='cache\livetalking\inductor';TRITON_CACHE_DIR='cache\livetalking\triton'}
foreach($LtName in $LtDirs.Keys){$LtPath=Join-Path $LtRoot $LtDirs[$LtName];[IO.Directory]::CreateDirectory($LtPath)|Out-Null;[Environment]::SetEnvironmentVariable($LtName,$LtPath,'Process')}
$env:HF_HUB_OFFLINE='1';$env:TRANSFORMERS_OFFLINE='1';$env:HF_HUB_DISABLE_TELEMETRY='1'
