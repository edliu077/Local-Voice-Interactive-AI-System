#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Common = Join-Path $ProjectRoot 'scripts\windows\common.ps1'
$PreviousRuntimeRoot = [Environment]::GetEnvironmentVariable('LVIAI_RUNTIME_ROOT', 'Process')
$TestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("lviai-launcher-test-" + [guid]::NewGuid().ToString('N'))
$StartedTestProcessId = $null
$ExpectedTestFragments = $null

try {
    New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null
    [Environment]::SetEnvironmentVariable('LVIAI_RUNTIME_ROOT', $TestRoot, 'Process')
    . $Common

    $PidDir = Join-Path $TestRoot 'pids'
    New-Item -ItemType Directory -Path $PidDir -Force | Out-Null

    # Dead stale PID recovery.
    $StalePidFile = Join-Path $PidDir 'test-stale.pid'
    $StaleStartingFile = Join-Path $PidDir 'test-stale.starting'
    [System.IO.File]::WriteAllText($StalePidFile, "99999999`r`n")
    Initialize-LviaiServiceStart 'test-stale' '127.0.0.1' 49151 @('LVIAI_NEVER_MATCH') $StalePidFile $StaleStartingFile
    if (Test-Path -LiteralPath $StalePidFile) { throw 'Dead stale PID file was not removed.' }

    # A live but unrelated PID is never stopped merely because it appears in a PID file.
    $UnrelatedPidFile = Join-Path $PidDir 'test-unrelated.pid'
    [System.IO.File]::WriteAllText($UnrelatedPidFile, "$PID`r`n")
    Stop-LviaiService 'test-unrelated' '127.0.0.1' 49152 @('LVIAI_NEVER_MATCH') 2
    if ($null -eq (Get-Process -Id $PID -ErrorAction SilentlyContinue)) { throw 'The unrelated test process was stopped.' }
    if (Test-Path -LiteralPath $UnrelatedPidFile) { throw 'Unrelated reused PID file was not removed.' }

    # A verified process that is still in its pre-listener startup phase can be stopped safely.
    $Node = (Get-Command node.exe -ErrorAction Stop).Source
    $StartingScript = Join-Path $TestRoot 'starting.js'
    [System.IO.File]::WriteAllText($StartingScript, "setInterval(()=>{},1000);")
    $StartingFragments = @($StartingScript, 'LVIAI_TEST_STARTING')
    $StartingProcess = Start-Process -FilePath $Node -ArgumentList @($StartingScript, 'LVIAI_TEST_STARTING') -WorkingDirectory $TestRoot -WindowStyle Hidden -PassThru
    $StartingMarker = Join-Path $PidDir 'test-starting.starting'
    [System.IO.File]::WriteAllText($StartingMarker, "$($StartingProcess.Id)`r`n")
    Stop-LviaiService 'test-starting' '127.0.0.1' 49153 $StartingFragments 10
    if ($null -ne (Get-Process -Id $StartingProcess.Id -ErrorAction SilentlyContinue)) { throw 'Verified startup process remained after safe stop.' }
    if (Test-Path -LiteralPath $StartingMarker) { throw 'Verified startup marker was not removed.' }

    # An unknown listener causes a fail-closed refusal and is not killed.
    $GuardListener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $GuardListener.Start()
    try {
        $GuardPort = ([System.Net.IPEndPoint]$GuardListener.LocalEndpoint).Port
        $Refused = $false
        try {
            Initialize-LviaiServiceStart 'test-guard' '127.0.0.1' $GuardPort @('LVIAI_NEVER_MATCH') (Join-Path $PidDir 'test-guard.pid') (Join-Path $PidDir 'test-guard.starting')
        } catch {
            $Refused = $_.Exception.Message -like '*unverified process*'
        }
        if (-not $Refused) { throw 'Unknown listener was not rejected.' }
        if (-not $GuardListener.Server.IsBound) { throw 'Unknown listener was unexpectedly stopped.' }
    } finally {
        $GuardListener.Stop()
    }

    # Start a disposable Node listener, verify listener-PID writeback, then stop only that PID.
    $Probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $Probe.Start()
    $TestPort = ([System.Net.IPEndPoint]$Probe.LocalEndpoint).Port
    $Probe.Stop()
    $ListenerScript = Join-Path $TestRoot 'listener.js'
    [System.IO.File]::WriteAllText(
        $ListenerScript,
        "const http=require('http');const port=Number(process.argv[2]);http.createServer((req,res)=>res.end('ok')).listen(port,'127.0.0.1');"
    )
    $ExpectedTestFragments = @($ListenerScript, 'LVIAI_TEST_LISTENER')
    $Started = Start-LviaiLoggedProcess 'test-listener' $Node @($ListenerScript, "$TestPort", 'LVIAI_TEST_LISTENER') $TestRoot '127.0.0.1' $TestPort $ExpectedTestFragments 15
    $StartedTestProcessId = $Started.ProcessId
    $Recorded = [int](Get-Content -LiteralPath $Started.PidFile -Raw).Trim()
    $ListenerOwner = Get-LviaiListenerProcessId '127.0.0.1' $TestPort
    if ($Recorded -ne $ListenerOwner -or $Recorded -ne $Started.ProcessId) {
        throw "PID writeback mismatch: recorded=$Recorded listener=$ListenerOwner returned=$($Started.ProcessId)"
    }
    Stop-LviaiService 'test-listener' '127.0.0.1' $TestPort $ExpectedTestFragments 10
    if ($null -ne (Get-LviaiListenerProcessId '127.0.0.1' $TestPort)) { throw 'Test listener remained after safe stop.' }
    $StartedTestProcessId = $null

    Write-Host 'Launcher hardening tests passed.'
} finally {
    if ($null -ne $StartedTestProcessId -and $null -ne (Get-Process -Id $StartedTestProcessId -ErrorAction SilentlyContinue)) {
        if ($null -ne $ExpectedTestFragments -and (Test-LviaiProcessIdentity $StartedTestProcessId $ExpectedTestFragments)) {
            Stop-Process -Id $StartedTestProcessId -ErrorAction SilentlyContinue
        }
    }
    [Environment]::SetEnvironmentVariable('LVIAI_RUNTIME_ROOT', $PreviousRuntimeRoot, 'Process')
    if (Test-Path -LiteralPath $TestRoot -PathType Container) {
        $ResolvedTestRoot = (Resolve-Path -LiteralPath $TestRoot).Path
        $ResolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if ($ResolvedTestRoot.StartsWith($ResolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and $ResolvedTestRoot -like '*lviai-launcher-test-*') {
            Remove-Item -LiteralPath $ResolvedTestRoot -Recurse -Force
        }
    }
}
