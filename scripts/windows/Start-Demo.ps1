#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$Launchers = @(
    @{ Name = 'LLM'; Script = 'start-llm.ps1' },
    @{ Name = 'STT'; Script = 'start-stt.ps1' },
    @{ Name = 'TTS'; Script = 'start-tts.ps1' },
    @{ Name = 'WebSocket'; Script = 'start-websocket.ps1' },
    @{ Name = 'Frontend'; Script = 'start-frontend.ps1' }
)

foreach ($Launcher in $Launchers) {
    $LauncherPath = Require-LviaiFile (Join-Path $PSScriptRoot $Launcher.Script) "$($Launcher.Name) launcher"
    Write-Host "Starting $($Launcher.Name)..."
    try {
        & $LauncherPath
    } catch {
        Write-Error "$($Launcher.Name) startup failed. The sequence has stopped. Run Stop-Demo.ps1 to safely stop services that were already started. $($_.Exception.Message)"
        throw
    }
}

$Checks = @(
    @{ Name = 'Frontend'; Host = Get-LviaiLoopbackHost 'LVIAI_FRONTEND_HOST'; Port = Get-LviaiPort 'LVIAI_FRONTEND_PORT' 3000 },
    @{ Name = 'LLM'; Host = Get-LviaiLoopbackHost 'LVIAI_LLM_HOST'; Port = Get-LviaiPort 'LVIAI_LLM_PORT' 8080 },
    @{ Name = 'TTS'; Host = Get-LviaiLoopbackHost 'LVIAI_TTS_HOST'; Port = Get-LviaiPort 'LVIAI_TTS_PORT' 8765 },
    @{ Name = 'STT'; Host = Get-LviaiLoopbackHost 'LVIAI_STT_HOST'; Port = Get-LviaiPort 'LVIAI_STT_PORT' 8766 },
    @{ Name = 'WebSocket'; Host = Get-LviaiLoopbackHost 'LVIAI_WS_HOST'; Port = Get-LviaiPort 'LVIAI_WS_PORT' 8767 }
)
foreach ($Check in $Checks) {
    $ListenerId = Get-LviaiListenerProcessId $Check.Host $Check.Port
    if ($null -eq $ListenerId) { throw "$($Check.Name) lost its listener on $($Check.Host):$($Check.Port)." }
    Write-Host "$($Check.Name) listener confirmed on $($Check.Host):$($Check.Port) (PID $ListenerId)."
}

$FrontendUrl = "http://127.0.0.1:$(Get-LviaiPort 'LVIAI_FRONTEND_PORT' 3000)/"
Write-Host "All Demo Stable services are ready. Opening $FrontendUrl"
Start-Process $FrontendUrl
