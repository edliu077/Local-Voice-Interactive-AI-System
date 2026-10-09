#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:LviaiDerivedRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path

function Import-LviaiDotEnv {
    $EnvFile = Join-Path $script:LviaiDerivedRoot '.env'
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) { return }
    foreach ($Line in Get-Content -LiteralPath $EnvFile -Encoding utf8) {
        $Trimmed = $Line.Trim()
        if (-not $Trimmed -or $Trimmed.StartsWith('#')) { continue }
        if ($Trimmed -notmatch '^((?:NEXT_PUBLIC_)?LVIAI_[A-Z0-9_]+)=(.*)$') {
            throw "Invalid .env line. Only LVIAI_* and NEXT_PUBLIC_LVIAI_* assignments are accepted."
        }
        $Name = $Matches[1]
        $Value = $Matches[2].Trim()
        if (($Value.StartsWith('"') -and $Value.EndsWith('"')) -or ($Value.StartsWith("'") -and $Value.EndsWith("'"))) {
            $Value = $Value.Substring(1, $Value.Length - 2)
        }
        if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($Name, 'Process'))) {
            [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
        }
    }
}

Import-LviaiDotEnv

$ConfiguredRoot = [Environment]::GetEnvironmentVariable('LVIAI_PROJECT_ROOT', 'Process')
if ([string]::IsNullOrWhiteSpace($ConfiguredRoot)) {
    $script:LviaiProjectRoot = $script:LviaiDerivedRoot
} else {
    if (-not [System.IO.Path]::IsPathRooted($ConfiguredRoot)) { throw 'LVIAI_PROJECT_ROOT must be absolute.' }
    $script:LviaiProjectRoot = (Resolve-Path -LiteralPath $ConfiguredRoot).Path
}
if (-not (Test-Path -LiteralPath $script:LviaiProjectRoot -PathType Container)) {
    throw "Demo Stable project root is missing: $script:LviaiProjectRoot"
}

function Get-LviaiPath([string]$Name, [string]$DefaultPath) {
    $Value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($Value)) { $Value = $DefaultPath }
    if (-not [System.IO.Path]::IsPathRooted($Value)) { throw "$Name must be an absolute path." }
    return [System.IO.Path]::GetFullPath($Value)
}

function Require-LviaiFile([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "$Label is missing: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Require-LviaiDirectory([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { throw "$Label is missing: $Path" }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-LviaiLoopbackHost([string]$Name) {
    $Value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($Value)) { $Value = '127.0.0.1' }
    if ($Value -ne '127.0.0.1') { throw "$Name must remain 127.0.0.1." }
    return $Value
}

function Get-LviaiPort([string]$Name, [int]$DefaultPort) {
    $Raw = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ([string]::IsNullOrWhiteSpace($Raw)) { return $DefaultPort }
    $Parsed = 0
    if (-not [int]::TryParse($Raw, [ref]$Parsed) -or $Parsed -lt 1 -or $Parsed -gt 65535) {
        throw "$Name must be an integer between 1 and 65535."
    }
    return $Parsed
}

function Get-LviaiListenerProcessId([string]$Address, [int]$ListenPort) {
    # Get-NetTCPConnection can retain a stale row after its owning PID exits and
    # that PID may later be reused. netstat reflects the live listener table and
    # is therefore the ownership source of truth for start/stop decisions.
    $Pattern = '^\s*TCP\s+\S+:' + [regex]::Escape("$ListenPort") + '\s+\S+\s+LISTENING\s+(\d+)\s*$'
    $ProcessIds = @(
        foreach ($Line in (& netstat.exe -ano -p tcp 2>$null)) {
            if ($Line -match $Pattern) {
                $CandidateId = [int]$Matches[1]
                if ($null -ne (Get-Process -Id $CandidateId -ErrorAction SilentlyContinue)) { $CandidateId }
            }
        }
    ) | Select-Object -Unique
    $ProcessIds = @($ProcessIds)
    if ($ProcessIds.Count -gt 1) {
        throw "Port $ListenPort has multiple listener owners; refusing ambiguous ownership."
    }
    if ($ProcessIds.Count -eq 1) { return [int]$ProcessIds[0] }
    return $null
}

function Get-LviaiProcessCommandLine([int]$TargetProcessId) {
    try {
        $Info = Get-CimInstance Win32_Process -Filter "ProcessId = $TargetProcessId" -ErrorAction Stop
        return [string]$Info.CommandLine
    } catch {
        return $null
    }
}

function Test-LviaiProcessIdentity([int]$TargetProcessId, [string[]]$ExpectedCommandFragments) {
    if ($null -eq (Get-Process -Id $TargetProcessId -ErrorAction SilentlyContinue)) { return $false }
    $CommandLine = Get-LviaiProcessCommandLine $TargetProcessId
    if ([string]::IsNullOrWhiteSpace($CommandLine)) { return $false }
    foreach ($Fragment in $ExpectedCommandFragments) {
        if ([string]::IsNullOrWhiteSpace($Fragment)) { continue }
        if ($CommandLine.IndexOf($Fragment, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
    }
    return $true
}

function Write-LviaiPidFile([string]$PidFile, [int]$ListenerProcessId) {
    [System.IO.File]::WriteAllText($PidFile, "$ListenerProcessId`r`n", [System.Text.UTF8Encoding]::new($false))
}

function Initialize-LviaiServiceStart(
    [string]$Name,
    [string]$Address,
    [int]$ListenPort,
    [string[]]$ExpectedCommandFragments,
    [string]$PidFile,
    [string]$StartingFile
) {
    foreach ($Marker in @($StartingFile, $PidFile)) {
        if (-not (Test-Path -LiteralPath $Marker -PathType Leaf)) { continue }
        $RecordedText = (Get-Content -LiteralPath $Marker -Raw).Trim()
        $RecordedId = 0
        if (-not [int]::TryParse($RecordedText, [ref]$RecordedId) -or $RecordedId -le 0) {
            Remove-Item -LiteralPath $Marker -Force
            Write-Host "Removed invalid stale marker for ${Name}: $Marker"
            continue
        }
        $RecordedProcess = Get-Process -Id $RecordedId -ErrorAction SilentlyContinue
        if ($null -eq $RecordedProcess) {
            Remove-Item -LiteralPath $Marker -Force
            Write-Host "Removed dead stale marker for $Name (PID $RecordedId)."
            continue
        }
        $ListenerId = Get-LviaiListenerProcessId $Address $ListenPort
        if ($null -ne $ListenerId -and (Test-LviaiProcessIdentity $ListenerId $ExpectedCommandFragments)) {
            Write-LviaiPidFile $PidFile $ListenerId
            if ($Marker -ne $PidFile) { Remove-Item -LiteralPath $Marker -Force }
            throw "$Name is already listening at ${Address}:$ListenPort (PID $ListenerId)."
        }
        if (Test-LviaiProcessIdentity $RecordedId $ExpectedCommandFragments) {
            throw "$Name has a verified startup/server process (PID $RecordedId) but no verified listener yet; refusing a duplicate start."
        }
        Remove-Item -LiteralPath $Marker -Force
        Write-Host "Removed reused/unrelated stale marker for $Name (PID $RecordedId) without stopping that process."
    }

    $ExistingListenerId = Get-LviaiListenerProcessId $Address $ListenPort
    if ($null -ne $ExistingListenerId) {
        if (Test-LviaiProcessIdentity $ExistingListenerId $ExpectedCommandFragments) {
            Write-LviaiPidFile $PidFile $ExistingListenerId
            throw "$Name is already listening at ${Address}:$ListenPort (PID $ExistingListenerId); repaired its PID file."
        }
        throw "Port $ListenPort is owned by an unverified process (PID $ExistingListenerId); refusing to overwrite or stop it."
    }
}

function Start-LviaiLoggedProcess(
    [string]$Name,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$Address,
    [int]$ListenPort,
    [string[]]$ExpectedCommandFragments,
    [int]$ListenerTimeoutSeconds = 60
) {
    $RuntimeRoot = Get-LviaiPath 'LVIAI_RUNTIME_ROOT' (Join-Path $script:LviaiProjectRoot 'runtime')
    $LogDir = Join-Path $RuntimeRoot 'logs'
    $PidDir = Join-Path $RuntimeRoot 'pids'
    New-Item -ItemType Directory -Path $LogDir, $PidDir -Force | Out-Null
    $Stdout = Join-Path $LogDir "$Name-stdout.txt"
    $Stderr = Join-Path $LogDir "$Name-stderr.txt"
    $PidFile = Join-Path $PidDir "$Name.pid"
    $StartingFile = Join-Path $PidDir "$Name.starting"

    Initialize-LviaiServiceStart $Name $Address $ListenPort $ExpectedCommandFragments $PidFile $StartingFile

    $Process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -PassThru
    [System.IO.File]::WriteAllText($StartingFile, "$($Process.Id)`r`n", [System.Text.UTF8Encoding]::new($false))

    $Deadline = [DateTime]::UtcNow.AddSeconds($ListenerTimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        $ListenerId = Get-LviaiListenerProcessId $Address $ListenPort
        if ($null -ne $ListenerId) {
            if (-not (Test-LviaiProcessIdentity $ListenerId $ExpectedCommandFragments)) {
                throw "$Name port $ListenPort was claimed by an unverified process (PID $ListenerId). No PID file was written."
            }
            Write-LviaiPidFile $PidFile $ListenerId
            Remove-Item -LiteralPath $StartingFile -Force -ErrorAction SilentlyContinue
            Write-Host "$Name listener detected. PID=$ListenerId; logs=$LogDir"
            return [pscustomobject]@{
                Name = $Name
                ProcessId = $ListenerId
                Stdout = $Stdout
                Stderr = $Stderr
                PidFile = $PidFile
            }
        }
        Start-Sleep -Milliseconds 500
    }

    if ($null -eq (Get-Process -Id $Process.Id -ErrorAction SilentlyContinue) -or -not (Test-LviaiProcessIdentity $Process.Id $ExpectedCommandFragments)) {
        Remove-Item -LiteralPath $StartingFile -Force -ErrorAction SilentlyContinue
    }
    throw "$Name did not create a verified listener on ${Address}:$ListenPort within $ListenerTimeoutSeconds seconds. See $Stdout and $Stderr"
}

function Wait-LviaiJsonHealth(
    [string]$Name,
    [string]$Uri,
    [string]$ExpectedStatus,
    [int]$TimeoutSeconds,
    [string]$Stdout,
    [string]$Stderr
) {
    $Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $LastStatus = 'unreachable'
    while ([DateTime]::UtcNow -lt $Deadline) {
        try {
            $Response = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 4
            $LastStatus = [string]$Response.status
            if ($LastStatus -eq $ExpectedStatus) {
                Write-Host "$Name health ready: $Uri (status=$LastStatus)"
                return
            }
        } catch {
            $LastStatus = $_.Exception.Message
        }
        Start-Sleep -Milliseconds 750
    }
    throw "$Name health did not reach status '$ExpectedStatus' within $TimeoutSeconds seconds (last=$LastStatus). See $Stdout and $Stderr"
}

function Wait-LviaiHttpOk(
    [string]$Name,
    [string]$Uri,
    [int]$TimeoutSeconds,
    [string]$Stdout,
    [string]$Stderr
) {
    $Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 4
            if ($Response.StatusCode -eq 200) {
                Write-Host "$Name HTTP ready: $Uri"
                return
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not return HTTP 200 within $TimeoutSeconds seconds. See $Stdout and $Stderr"
}

function Stop-LviaiService(
    [string]$Name,
    [string]$Address,
    [int]$ListenPort,
    [string[]]$ExpectedCommandFragments,
    [int]$TimeoutSeconds = 20
) {
    $RuntimeRoot = Get-LviaiPath 'LVIAI_RUNTIME_ROOT' (Join-Path $script:LviaiProjectRoot 'runtime')
    $PidDir = Join-Path $RuntimeRoot 'pids'
    $PidFile = Join-Path $PidDir "$Name.pid"
    $StartingFile = Join-Path $PidDir "$Name.starting"
    $RecordedId = $null

    if (Test-Path -LiteralPath $PidFile -PathType Leaf) {
        $RecordedText = (Get-Content -LiteralPath $PidFile -Raw).Trim()
        $ParsedId = 0
        if ([int]::TryParse($RecordedText, [ref]$ParsedId) -and $ParsedId -gt 0) {
            $RecordedId = $ParsedId
        } else {
            Remove-Item -LiteralPath $PidFile -Force
            Write-Host "Removed invalid stale PID file for $Name."
        }
    }

    if ($null -eq $RecordedId -and (Test-Path -LiteralPath $StartingFile -PathType Leaf)) {
        $StartingText = (Get-Content -LiteralPath $StartingFile -Raw).Trim()
        $StartingId = 0
        if ([int]::TryParse($StartingText, [ref]$StartingId) -and $StartingId -gt 0 -and
            $null -ne (Get-Process -Id $StartingId -ErrorAction SilentlyContinue) -and
            (Test-LviaiProcessIdentity $StartingId $ExpectedCommandFragments)) {
            $RecordedId = $StartingId
            Write-Host "Using verified startup marker for $Name (PID $StartingId)."
        } else {
            Remove-Item -LiteralPath $StartingFile -Force
            Write-Host "Removed invalid, dead, or unrelated startup marker for $Name."
        }
    }

    $ListenerId = Get-LviaiListenerProcessId $Address $ListenPort
    $TargetId = $null
    if ($null -ne $ListenerId) {
        if (-not (Test-LviaiProcessIdentity $ListenerId $ExpectedCommandFragments)) {
            throw "Refusing to stop unverified listener on port $ListenPort (PID $ListenerId)."
        }
        if ($null -eq $RecordedId) {
            throw "Verified $Name listener PID $ListenerId has no project PID file; refusing an unmanaged stop."
        }
        $TargetId = $ListenerId
        if ($RecordedId -ne $ListenerId) {
            Write-Host "Reconciled $Name PID file from wrapper/stale PID $RecordedId to listener PID $ListenerId."
            Write-LviaiPidFile $PidFile $ListenerId
        }
    } elseif ($null -ne $RecordedId) {
        $RecordedProcess = Get-Process -Id $RecordedId -ErrorAction SilentlyContinue
        if ($null -eq $RecordedProcess) {
            Remove-Item -LiteralPath $PidFile -Force
            Remove-Item -LiteralPath $StartingFile -Force -ErrorAction SilentlyContinue
            Write-Host "Removed dead stale PID file for $Name (PID $RecordedId)."
            return
        }
        if (-not (Test-LviaiProcessIdentity $RecordedId $ExpectedCommandFragments)) {
            Remove-Item -LiteralPath $PidFile -Force
            Write-Host "Removed reused/unrelated PID file for $Name without stopping PID $RecordedId."
            return
        }
        $TargetId = $RecordedId
    } else {
        Remove-Item -LiteralPath $StartingFile -Force -ErrorAction SilentlyContinue
        Write-Host "$Name is not running."
        return
    }

    if (-not (Test-LviaiProcessIdentity $TargetId $ExpectedCommandFragments)) {
        throw "Identity changed before stop for $Name PID $TargetId; refusing to stop it."
    }
    Stop-Process -Id $TargetId -ErrorAction Stop
    $Deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $Deadline) {
        $StillAlive = $null -ne (Get-Process -Id $TargetId -ErrorAction SilentlyContinue)
        $StillListening = $null -ne (Get-LviaiListenerProcessId $Address $ListenPort)
        if (-not $StillAlive -and -not $StillListening) { break }
        Start-Sleep -Milliseconds 250
    }
    if ($null -ne (Get-Process -Id $TargetId -ErrorAction SilentlyContinue) -or $null -ne (Get-LviaiListenerProcessId $Address $ListenPort)) {
        throw "$Name PID $TargetId did not stop cleanly within $TimeoutSeconds seconds."
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StartingFile -Force -ErrorAction SilentlyContinue
    Write-Host "$Name stopped safely (PID $TargetId)."
}
