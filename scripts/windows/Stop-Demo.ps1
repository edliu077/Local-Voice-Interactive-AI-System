#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$Frontend = Join-Path $script:LviaiProjectRoot 'frontend'
$NextCli = Join-Path $Frontend 'node_modules\next\dist\bin\next'
$SttService = Join-Path $script:LviaiProjectRoot 'backend\stt\stt_service.py'
$TtsServiceMarker = 'tts_service:app'
$WebSocketService = Join-Path $script:LviaiProjectRoot 'backend\orchestrator\voice_ws_server.py'
$LlamaServer = Get-LviaiPath 'LVIAI_LLAMA_SERVER' (Join-Path $script:LviaiProjectRoot 'tools\llama.cpp\llama-server.exe')

$Services = @(
    @{ Name = 'frontend'; Host = Get-LviaiLoopbackHost 'LVIAI_FRONTEND_HOST'; Port = Get-LviaiPort 'LVIAI_FRONTEND_PORT' 3000; Fragments = @($NextCli, 'start') },
    @{ Name = 'websocket'; Host = Get-LviaiLoopbackHost 'LVIAI_WS_HOST'; Port = Get-LviaiPort 'LVIAI_WS_PORT' 8767; Fragments = @($WebSocketService) },
    @{ Name = 'tts'; Host = Get-LviaiLoopbackHost 'LVIAI_TTS_HOST'; Port = Get-LviaiPort 'LVIAI_TTS_PORT' 8765; Fragments = @('uvicorn', $TtsServiceMarker) },
    @{ Name = 'stt'; Host = Get-LviaiLoopbackHost 'LVIAI_STT_HOST'; Port = Get-LviaiPort 'LVIAI_STT_PORT' 8766; Fragments = @($SttService) },
    @{ Name = 'llm'; Host = Get-LviaiLoopbackHost 'LVIAI_LLM_HOST'; Port = Get-LviaiPort 'LVIAI_LLM_PORT' 8080; Fragments = @([System.IO.Path]::GetFileName($LlamaServer), 'lviai-qwen3') }
)

$Failures = New-Object System.Collections.Generic.List[string]
foreach ($Service in $Services) {
    try {
        Stop-LviaiService $Service.Name $Service.Host $Service.Port $Service.Fragments 20
    } catch {
        $Message = "$($Service.Name): $($_.Exception.Message)"
        $Failures.Add($Message)
        Write-Warning $Message
    }
}

foreach ($Service in $Services) {
    $ListenerId = Get-LviaiListenerProcessId $Service.Host $Service.Port
    if ($null -ne $ListenerId) {
        $Failures.Add("$($Service.Name): port $($Service.Port) is still listening (PID $ListenerId)")
    }
}

if ($Failures.Count -gt 0) {
    throw "Demo Stable shutdown was incomplete: $($Failures -join '; ')"
}
Write-Host 'All Demo Stable listeners stopped safely.'
