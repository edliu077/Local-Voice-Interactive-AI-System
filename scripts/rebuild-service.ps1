#requires -Version 5.1
param(
    [Parameter(Mandatory=$true)][ValidateSet('preflight','help','start','stop','status')][string]$Action,
    [ValidateSet('llm','stt','tts','ws','frontend')][string]$Service = 'llm',
    [ValidateSet('4b','4b-hybrid','1.7b')][string]$Profile,
    [ValidateSet('browser','winsound')][string]$Playback = 'browser',
    [string]$RecoveryEvidence
)
$ErrorActionPreference = 'Stop'
$Workspace = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$Settings = Get-Content -LiteralPath (Join-Path $Workspace 'config\rebuild.json') -Raw | ConvertFrom-Json
if (-not $Profile) { $Profile = $Settings.default_llm_profile }
if ($Profile -notin @('4b','4b-hybrid','1.7b')) { throw 'Unknown LLM profile' }
if ($Action -in @('start','preflight','help') -and $Profile -ne $Settings.default_llm_profile) { throw 'LLM profile retired; only the configured default may start. Historical stop/status remain identity checked.' }
$Llm = $Settings.llm_profiles.$Profile
$IsHybrid = $Profile -eq '4b-hybrid'
if ($IsHybrid -and $Service -ne 'llm') { throw 'Hybrid profile is restricted to the independent LLM service' }
$GpuLayers = if ($IsHybrid) { [int]$Llm.gpu_layers } else { 0 }
$Key = if ($Service -eq 'llm') { "llm-$Profile" } else { $Service }
$Runtime = Join-Path $Workspace "runtime\services-live\$Key"
$RecordPath = Join-Path $Runtime 'owner.json'
$Stdout = Join-Path $Runtime 'stdout.log'
$Stderr = Join-Path $Runtime 'stderr.log'
. (Join-Path $PSScriptRoot 'rebuild-process-identity.ps1')

function Assert-OwnedPath([string]$Path) {
    $Absolute = [IO.Path]::GetFullPath($Path)
    if (-not $Absolute.StartsWith($Workspace+'\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Write path escaped Rebuild' }
    $Cursor = $Absolute
    while ($Cursor -and $Cursor.Length -ge $Workspace.Length) {
        if (Test-Path -LiteralPath $Cursor) {
            if ((Get-Item -LiteralPath $Cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point refused: $Cursor" }
        }
        $Cursor = Split-Path $Cursor -Parent
    }
}
Assert-OwnedPath $Runtime
Assert-OwnedPath (Join-Path $Workspace 'cache')
foreach ($File in @($RecordPath,$Stdout,$Stderr,(Join-Path $Runtime 'help.stdout.txt'),(Join-Path $Runtime 'help.stderr.txt'),(Join-Path $Runtime 'preflight.json'),(Join-Path $Runtime 'startup.json'))) { Assert-OwnedPath $File }

function Set-RebuildEnvironment {
    # Do not inherit hidden model/download/server options from another project.
    foreach ($Variable in @(Get-ChildItem Env: | Where-Object Name -like 'LLAMA_ARG_*')) {
        [Environment]::SetEnvironmentVariable($Variable.Name,$null,'Process')
    }
    if ($IsHybrid) { [Environment]::SetEnvironmentVariable('GGML_CUDA_ENABLE_UNIFIED_MEMORY',$null,'Process') }
    $env:REBUILD_LLM_PROFILE = $Profile
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONPATH = $Workspace
    $env:CYBER_PLAYBACK_MODE = $Playback
    $env:HF_HUB_OFFLINE = '1'
    $env:TRANSFORMERS_OFFLINE = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $Folders = @{
        HF_HOME='cache\hf'; HUGGINGFACE_HUB_CACHE='cache\hf\hub'; HF_HUB_CACHE='cache\hf\hub'
        TRANSFORMERS_CACHE='cache\hf\transformers'; TORCH_HOME='cache\torch'
        TORCHINDUCTOR_CACHE_DIR='cache\torchinductor'; TRITON_CACHE_DIR='cache\triton'
        CUDA_CACHE_PATH='cache\cuda'; XDG_CACHE_HOME='cache'; NUMBA_CACHE_DIR='cache\numba'
        PYTHONPYCACHEPREFIX='cache\pycache'; LLAMA_CACHE='cache\llama'; TEMP='runtime\tmp'; TMP='runtime\tmp'
    }
    foreach ($Name in $Folders.Keys) {
        $Path = Join-Path $Workspace $Folders[$Name]
        Assert-OwnedPath $Path
        [IO.Directory]::CreateDirectory($Path) | Out-Null
        [Environment]::SetEnvironmentVariable($Name,$Path,'Process')
    }
    [IO.Directory]::CreateDirectory($Runtime) | Out-Null
}

function Assert-HybridRuntime {
    if (-not $IsHybrid) { return }
    if ($GpuLayers -ne 7 -or $Llm.minimum_gpu_free_mib -lt 2558 -or $Llm.device -cne 'CUDA0' -or
        $Llm.model -cne $Settings.llm_profiles.'4b'.model -or $Llm.alias -cne $Settings.llm_profiles.'4b'.alias -or $Llm.port -ne 8081) { throw 'Invalid conservative hybrid profile' }
    $Manifest=Join-Path $Workspace $Llm.runtime_manifest
    Assert-OwnedPath $Manifest
    Assert-OwnedPath $Llm.executable
    if ((Get-FileHash -LiteralPath $Manifest).Hash -cne $Llm.runtime_manifest_sha256) { throw 'CUDA runtime manifest changed' }
    $Rows=@(Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json)
    foreach ($Row in $Rows) {
        $Path=Join-Path $Workspace $Row.path;Assert-OwnedPath $Path
        if ((Get-FileHash -LiteralPath $Path).Hash.ToLowerInvariant() -cne $Row.sha256) { throw "CUDA runtime file changed: $($Row.path)" }
    }
    $script:HybridBinarySHA256=(Get-FileHash -LiteralPath $Llm.executable).Hash
    $script:HybridExpectedNames=@($Rows | ForEach-Object {Split-Path $_.path -Leaf})
}
Assert-HybridRuntime

$Program = $null; $LaunchArgs = @(); $Port = 0; $Health = $null
switch ($Service) {
    'llm' {
        $Program = if ($IsHybrid) { $Llm.executable } else { $Settings.llama_server }; $Port = [int]$Llm.port
        $LaunchArgs = @('-m',$Llm.model,'--host','127.0.0.1','--port',"$Port",'-ngl',"$GpuLayers",'-c','4096','-t','10','-tb','12','-np','1','--alias',$Llm.alias,'--reasoning','off')
        if ($IsHybrid) { $LaunchArgs += @('--device',$Llm.device,'--fit','off','--verbosity','4') }
        $Health = "http://127.0.0.1:$Port/health"
    }
    'stt' {
        $Program=Join-Path $Workspace '.venv-cpu\Scripts\python.exe'; $Port=8766
        $LaunchArgs=@('-B','-s',(Join-Path $Workspace 'experiments\persistent-stt-h1\service\stt_service.py'))
        $Health='http://127.0.0.1:8766/health'
    }
    'tts' {
        $Program=Join-Path $Workspace '.venv-tts\Scripts\python.exe'; $Port=8765
        $LaunchArgs=@('-B','-s','-m','uvicorn','experiments.qwen3-tts-e0.service.tts_service:app','--host','127.0.0.1','--port','8765','--no-access-log')
        $Health='http://127.0.0.1:8765/health'
    }
    'ws' {
        $Program=Join-Path $Workspace '.venv-cpu\Scripts\python.exe'; $Port=8767
        $LaunchArgs=@('-B','-s',(Join-Path $Workspace 'experiments\websocket-i0\server\voice_ws_server.py'),'--host','127.0.0.1','--port','8767')
    }
    'frontend' {
        # Frontend requires a future isolated dependency installation. Do not
        # accidentally run the original project's Next CLI via NODE_PATH.
        throw 'Frontend runtime remains disabled in Stage 2: no Rebuild node_modules installed. No old frontend will be started or stopped.'
    }
}

function ConvertTo-RebuildUtcTicks([object]$Value) {
    # Exact 100 ns .NET ticks: no rounding or tolerance that could hide PID reuse.
    if ($Value -is [DateTimeOffset]) { return $Value.UtcDateTime.Ticks }
    if ($Value -is [DateTime]) {
        if ($Value.Kind -eq [DateTimeKind]::Unspecified) { throw 'Process creation time has no timezone; identity check refused' }
        return $Value.ToUniversalTime().Ticks
    }
    if ($Value -isnot [string] -or $Value -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|[+-]\d{2}:\d{2})$') {
        throw 'Invalid process creation timestamp; identity check refused'
    }
    $Parsed = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse($Value, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$Parsed)) {
        throw 'Invalid process creation timestamp; identity check refused'
    }
    return $Parsed.UtcDateTime.Ticks
}

function Read-OwnedProcess {
    if (-not (Test-Path -LiteralPath $RecordPath)) { return $null }
    $Record = Get-Content -LiteralPath $RecordPath -Raw | ConvertFrom-Json
    if ($Record.Workspace -ne $Workspace -or $Record.Key -ne $Key -or $Record.Executable -ne $Program -or $Record.Arguments -cne ($LaunchArgs -join "`n")) {
        throw 'Owner record does not match this Rebuild service configuration; refusing process operation'
    }
    if ($Service -eq 'llm' -and $Profile -eq $Settings.default_llm_profile -and
        ($Record.Profile -cne $Profile -or $Record.ModelPath -cne $Llm.model -or $Record.ModelAlias -cne $Llm.alias -or $Record.ModelSHA256 -cne $Llm.model_sha256)) { throw 'Default 1.7B owner model identity mismatch' }
    $Info = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$Record.ProcessId)" -ErrorAction Stop
    if ($null -eq $Info) { return [pscustomobject]@{Record=$Record;Info=$null} }
    if ($Info.ProcessId -ne $Record.ProcessId -or $Info.ExecutablePath -ne $Record.Executable -or $Info.CommandLine -cne $Record.CommandLine -or (ConvertTo-RebuildUtcTicks $Info.CreationDate) -ne (ConvertTo-RebuildUtcTicks $Record.CreatedUtc)) {
        throw 'PID identity changed; refusing to stop or adopt the process'
    }
    if ($Record.ConsoleRootIdentity) { Assert-RebuildExactIdentity $Record.ConsoleRootIdentity (Get-RebuildIdentity $Info) }
    if ($IsHybrid) {
        if ($Record.BinarySHA256 -cne $HybridBinarySHA256 -or $Record.RuntimeManifestSHA256 -cne $Llm.runtime_manifest_sha256) { throw 'Hybrid binary/dependency ownership mismatch' }
        $BinaryDirectory=Split-Path $Program -Parent
        foreach ($Module in (Get-Process -Id $Info.ProcessId -ErrorAction Stop).Modules) {
            if ($Module.ModuleName -in $HybridExpectedNames -and (Split-Path $Module.FileName -Parent) -ine $BinaryDirectory) { throw 'Hybrid loaded dependency outside verified runtime' }
        }
    }
    return [pscustomobject]@{Record=$Record;Info=$Info}
}

function Get-Listeners { @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq $Port) }

function Assert-ActiveModelResponse($Models) {
    $Match=@($Models.data | Where-Object id -CEQ $Llm.alias)
    # Exact model path/SHA is bound by the owner; GGUF tensor counts are recorded
    # separately, since an explicit output copy need not match a marketing label.
    if ($Match.Count -ne 1 -or $Match[0].meta.n_ctx -ne 4096 -or $Match[0].meta.n_params -le 0) { throw 'Active LLM model identity or context mismatch' }
}

function Stop-OwnedProcess {
    try { Stop-OwnedProcessChecked } catch {
        $Audit = Join-Path $Runtime ('identity-conflict-'+[Guid]::NewGuid().ToString('N')+'.json')
        Assert-OwnedPath $Audit
        [ordered]@{TimeUtc=[DateTime]::UtcNow.ToString('o');Error=$_.Exception.Message;OwnerPath=$RecordPath;
            Processes=@(Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -eq $script:CheckedRootPid -or $_.ParentProcessId -eq $script:CheckedRootPid} | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,CreationDate)} |
            ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Audit -Encoding utf8
        throw
    }
}

function Stop-OwnedProcessChecked {
    $Owned = Read-OwnedProcess
    if ($null -eq $Owned) { Write-Output 'No Rebuild owner record; no process touched.'; return }
    $script:CheckedRootPid = [int]$Owned.Record.ProcessId
    if ($null -eq $Owned.Info) {
        if (@(Get-Listeners).Count) { throw 'Root absent but port occupied; owner preserved' }
        $KnownChildren = @($Owned.Record.ConsoleChildren)
        if (@($KnownChildren | Where-Object {$_ -and (Get-Process -Id $_.Pid -ErrorAction SilentlyContinue)}).Count) { throw 'Root absent but recorded child remains; owner preserved' }
        Move-Item -LiteralPath $RecordPath -Destination (Join-Path $Runtime ('stopped-'+[Guid]::NewGuid().ToString('N')+'.json'))
        Write-Output 'Recorded root and children absent, port released; owner archived.'; return
    }
    if ($Service -eq 'llm') {
        Stop-LlmOwnedTree $Owned
        return
    }
    # venv python.exe may redirect through one child python.exe. Validate the
    # complete descendant tree before acting; unrelated children fail closed.
    $Candidates = [Collections.Generic.List[object]]::new()
    $Queue = [Collections.Generic.Queue[int]]::new()
    $Queue.Enqueue([int]$Owned.Info.ProcessId)
    while ($Queue.Count -gt 0) {
        $ParentId = $Queue.Dequeue()
        foreach ($Child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" -ErrorAction Stop)) {
            if ($Service -eq 'llm' -or $Child.Name -ne 'python.exe' -or -not $Child.CommandLine.Contains($Workspace) -or $Child.CreationDate -lt $Owned.Info.CreationDate) {
                throw 'Unverified descendant; no process stopped'
            }
            $Candidates.Add($Child); $Queue.Enqueue([int]$Child.ProcessId)
        }
    }
    $Candidates.Reverse()
    foreach ($Child in $Candidates) {
        $Now = Get-CimInstance Win32_Process -Filter "ProcessId = $($Child.ProcessId)" -ErrorAction Stop
        if ($Now -and $Now.CreationDate -eq $Child.CreationDate -and $Now.CommandLine -ceq $Child.CommandLine) { Stop-Process -Id $Now.ProcessId -ErrorAction Stop }
        elseif ($Now) { throw 'Child PID identity changed; stop refused' }
    }
    $Recheck = Read-OwnedProcess
    if ($Recheck.Info) { Stop-Process -Id $Recheck.Info.ProcessId -ErrorAction Stop }
    for ($Attempt=0; $Attempt -lt 60; $Attempt++) {
        if (-not (Get-Process -Id $Owned.Record.ProcessId -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 250
    }
    if (Get-Process -Id $Owned.Record.ProcessId -ErrorAction SilentlyContinue) { throw 'Owned process did not exit' }
    $RemainingListeners = @(Get-Listeners)
    # Do not terminate any newly occupied port; report it instead.
    if ($RemainingListeners.Count) { throw 'Owned process exited, but another listener remains; it was not touched' }
    Assert-OwnedPath $RecordPath
    Move-Item -LiteralPath $RecordPath -Destination (Join-Path $Runtime ("stopped-"+[Guid]::NewGuid().ToString('N')+'.json'))
    Write-Output 'Stopped only the verified Rebuild service instance.'
}

function Register-LlmConsoleChildren {
    $Owned=Read-OwnedProcess
    if (-not $Owned.Info) { throw 'Owned LLM exited during registration' }
    $RootIdentity=Get-RebuildIdentity $Owned.Info
    $Record=$Owned.Record
    if ($Record.ConsoleRootIdentity) { Assert-RebuildExactIdentity $Record.ConsoleRootIdentity $RootIdentity }
    $Children=@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($RootIdentity.Pid)" | ForEach-Object {
        $Identity=Get-RebuildIdentity $_
        Assert-RebuildConsoleShape $Identity $RootIdentity
        if (@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($Identity.Pid)").Count) { throw 'Unexpected console descendant' }
        $Previous=@($Record.ConsoleChildren | Where-Object Pid -eq $Identity.Pid)
        if ($Previous.Count) { Assert-RebuildConsoleIdentity $Previous[0] $Identity $Record.ConsoleRootIdentity $RootIdentity }
        $Identity
    })
    # Never discard a registered identity if its process is still present.
    foreach ($Previous in @($Record.ConsoleChildren)) {
        if ($Previous -and $Previous.Pid -notin $Children.Pid -and (Get-Process -Id $Previous.Pid -ErrorAction SilentlyContinue)) { throw 'Registered console left process tree' }
    }
    $Record | Add-Member -NotePropertyName ConsoleRootIdentity -NotePropertyValue $RootIdentity -Force
    $Record | Add-Member -NotePropertyName ConsoleChildren -NotePropertyValue $Children -Force
    $Record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $RecordPath -Encoding utf8
}

function Stop-LlmOwnedTree($Owned) {
    $RootIdentity=Get-RebuildIdentity $Owned.Info
    $ExpectedRoot=$Owned.Record.ConsoleRootIdentity
    $ExpectedChildren=@($Owned.Record.ConsoleChildren | Where-Object {$_})
    if ($RecoveryEvidence) {
        if ($Action -ne 'stop') { throw 'Recovery evidence only permitted for explicit stop' }
        Assert-OwnedPath $RecoveryEvidence
        $Evidence=Get-Content -LiteralPath $RecoveryEvidence -Raw | ConvertFrom-Json
        if ($Evidence.Workspace -cne $Workspace -or $Evidence.Key -cne $Key -or
            $Evidence.OwnerCommandLine -cne $Owned.Record.CommandLine -or
            (ConvertTo-RebuildUtcTicks $Evidence.OwnerCreatedUtc) -ne (ConvertTo-RebuildUtcTicks $Owned.Record.CreatedUtc)) { throw 'Recovery evidence does not bind to owner' }
        $ExpectedRoot=$Evidence.RootIdentity; $ExpectedChildren=@($Evidence.Children)
    }
    $Children=@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($RootIdentity.Pid)")
    if ($ExpectedRoot) { Assert-RebuildExactIdentity $ExpectedRoot $RootIdentity }
    if ($Children.Count -and -not $ExpectedRoot) { throw 'Legacy console requires explicit trusted recovery evidence' }
    foreach ($Child in $Children) {
        $Actual=Get-RebuildIdentity $Child
        $Match=@($ExpectedChildren | Where-Object Pid -eq $Actual.Pid)
        if ($Match.Count -ne 1) { throw 'Unexpected unregistered LLM child' }
        Assert-RebuildConsoleIdentity $Match[0] $Actual $ExpectedRoot $RootIdentity
        if (@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($Actual.Pid)").Count) { throw 'Unexpected console descendant' }
    }
    foreach ($Child in $ExpectedChildren) {
        if ($Child.Pid -notin $Children.ProcessId -and (Get-Process -Id $Child.Pid -ErrorAction SilentlyContinue)) { throw 'Registered child left owned tree' }
    }
    if (@(Get-Listeners | Where-Object {$_.OwningProcess -ne $RootIdentity.Pid -or $_.LocalAddress -ne '127.0.0.1'}).Count) { throw 'Unexpected listener identity; untouched' }
    $Audit=Join-Path $Runtime ('verified-stop-'+[Guid]::NewGuid().ToString('N')+'.json')
    [ordered]@{Root=$RootIdentity;Children=$ExpectedChildren;RecoveryEvidence=$RecoveryEvidence;TimeUtc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Audit -Encoding utf8
    # Keep handles open across the final check and termination; never kill by a reused PID.
    $Handles=[Collections.Generic.List[object]]::new()
    try {
        foreach ($Child in $Children) {
            $Handle=[Diagnostics.Process]::GetProcessById([int]$Child.ProcessId);$null=$Handle.Handle;$Handles.Add($Handle)
            $Now=Get-CimInstance Win32_Process -Filter "ProcessId = $($Child.ProcessId)"
            $Match=@($ExpectedChildren | Where-Object Pid -eq $Child.ProcessId)[0]
            Assert-RebuildConsoleIdentity $Match (Get-RebuildIdentity $Now) $ExpectedRoot (Get-RebuildIdentity (Read-OwnedProcess).Info)
        }
        $RootHandle=[Diagnostics.Process]::GetProcessById($RootIdentity.Pid);$null=$RootHandle.Handle;$Handles.Add($RootHandle)
        Assert-RebuildExactIdentity $RootIdentity (Get-RebuildIdentity (Read-OwnedProcess).Info)
        # Validate the entire tree again before any destructive operation.
        $NowIds=@(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($RootIdentity.Pid)" | Select-Object -ExpandProperty ProcessId)
        if ((($Children.ProcessId | Sort-Object) -join ',') -cne (($NowIds | Sort-Object) -join ',')) { throw 'LLM tree changed before stop' }
        foreach ($Handle in $Handles) { if (-not $Handle.HasExited) { $Handle.Kill(); if (-not $Handle.WaitForExit(15000)) { throw 'Verified process did not exit' } } }
    } finally { foreach ($Handle in $Handles) { $Handle.Dispose() } }
    if (Get-Process -Id $RootIdentity.Pid -ErrorAction SilentlyContinue) { throw 'Root remains; owner preserved' }
    if (@(Get-Listeners).Count) { throw 'Port remains occupied; owner preserved' }
    foreach ($Child in $ExpectedChildren) { if (Get-Process -Id $Child.Pid -ErrorAction SilentlyContinue) { throw 'Child remains; owner preserved' } }
    Move-Item -LiteralPath $RecordPath -Destination (Join-Path $Runtime ('stopped-'+[Guid]::NewGuid().ToString('N')+'.json'))
    Write-Output 'Stopped only exact-identity verified Rebuild LLM and registered console children; port released; owner archived.'
}

if ($Action -eq 'stop') { Stop-OwnedProcess; return }
if ($Action -eq 'status') {
    $Owned = Read-OwnedProcess
    if ($Owned -and $Owned.Info) {
        if ($Service -eq 'llm') {
            $Binding=@(Get-Listeners)
            if (-not $Binding.Count -or @($Binding | Where-Object {$_.OwningProcess -ne $Owned.Info.ProcessId -or $_.LocalAddress -ne '127.0.0.1'}).Count) { throw 'Owned loopback listener missing or changed' }
            $Response=Invoke-RestMethod -Uri $Health -TimeoutSec 3
            if ($Response.status -ne 'ok') { throw 'Owned LLM health not ready' }
            Assert-ActiveModelResponse (Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 3)
        }
        Write-Output "Owned process: $($Owned.Info.ProcessId)"
    } else { throw 'No running owned process' }
    return
}

Set-RebuildEnvironment
if (-not (Test-Path -LiteralPath $Program -PathType Leaf)) {
    throw "Missing isolated executable: $Program. No environment will be installed automatically."
}
if ($Action -eq 'help') {
    if ($Service -ne 'llm') { throw 'Help check is restricted to the native llama binary' }
    # A parameter probe only: do not include -m or load any model.
    Push-Location $Workspace
    try { & $Program --help 1> (Join-Path $Runtime 'help.stdout.txt') 2> (Join-Path $Runtime 'help.stderr.txt'); $Code=$LASTEXITCODE } finally { Pop-Location }
    if ($Code -ne 0) { throw "llama --help failed: $Code" }
    Write-Output 'Native llama help saved; no model loaded.'
    return
}

$Listeners = @(Get-Listeners)
$OtherLlms = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%llama%'" -ErrorAction Stop)
$OtherLlmOwners = @(Get-ChildItem -LiteralPath (Join-Path $Workspace 'runtime\services-live') -Directory | Where-Object Name -Like 'llm-*' | ForEach-Object { Join-Path $_.FullName 'owner.json' } | Where-Object { $_ -ine $RecordPath -and (Test-Path -LiteralPath $_) })
$Os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
$Available = [uint64]$Os.FreePhysicalMemory * 1KB
$ModelHash = $null
if ($Service -eq 'llm' -and $Profile -eq $Settings.default_llm_profile -and $Llm.model_sha256) {
    $ModelHash=(Get-FileHash -LiteralPath $Llm.model -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ModelHash -cne $Llm.model_sha256) { throw 'Active 1.7B model SHA256 mismatch; no process started' }
}
$Os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
$Available = [uint64]$Os.FreePhysicalMemory * 1KB
$Gpu = (& nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free --format=csv,noheader,nounits 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'GPU resource query failed; preflight incomplete' }
$ResourceJson = & (Join-Path $Workspace '.venv-livetalking\Scripts\python.exe') -B -s (Join-Path $PSScriptRoot 'resource-policy.py') --service "llm-$Profile"
if ($LASTEXITCODE -ne 0) { throw 'Resource evidence unavailable; no process started' }
$Resource = $ResourceJson | ConvertFrom-Json
$Available = [uint64]$Resource.available_ram_bytes
$MinimumAvailable = [uint64]$Resource.minimum_ram_bytes
$Preflight = [ordered]@{
    TimeUtc=[DateTime]::UtcNow.ToString('o');Service=$Service;Profile=$Profile;Port=$Port;Model=$Llm.model;ModelAlias=$Llm.alias;ModelSHA256=$ModelHash;GPUOffload=$GpuLayers;Context=4096
    AvailableRamBytes=$Available;MinimumAvailableRamBytes=$MinimumAvailable;GPU=$Gpu
    CommittedBytes=$Resource.committed_bytes;CommitLimitBytes=$Resource.commit_limit_bytes;CommitHeadroomBytes=$Resource.commit_headroom_bytes;ResourceErrors=@($Resource.resource_errors)
    Listeners=@($Listeners | Select-Object LocalAddress,LocalPort,OwningProcess)
    OtherLlmProcesses=@($OtherLlms | Select-Object ProcessId,Name,ExecutablePath,CreationDate);OtherLlmOwners=$OtherLlmOwners
    MinimumGpuFreeMiB=$(if($IsHybrid){[int]$Llm.minimum_gpu_free_mib}else{0})
    Status='READY_FOR_ISOLATED_START'
}
if ($Listeners.Count) { $Preflight.Status='BLOCKED_PORT_OCCUPIED' }
elseif ($Service -eq 'llm' -and @($Resource.resource_errors).Count) { $Preflight.Status='BLOCKED_LOW_MEMORY_OR_COMMIT' }
elseif ($Service -eq 'llm' -and $OtherLlms.Count) { $Preflight.Status='BLOCKED_OTHER_LLM_RUNNING' }
elseif ($Service -eq 'llm' -and $OtherLlmOwners.Count) { $Preflight.Status='BLOCKED_OTHER_LLM_OWNER' }
elseif ($IsHybrid -and [int]($Gpu.Split(',')[-1].Trim()) -lt [int]$Llm.minimum_gpu_free_mib) { $Preflight.Status='BLOCKED_GPU_MEMORY' }
if ($Service -eq 'llm' -and -not (Test-Path -LiteralPath $Llm.model -PathType Leaf)) { $Preflight.Status='BLOCKED_MODEL_MISSING' }
$Preflight | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $Runtime 'preflight.json') -Encoding utf8
if ($Action -eq 'preflight') { $Preflight | ConvertTo-Json -Depth 6; return }
if ($Preflight.Status -ne 'READY_FOR_ISOLATED_START') { throw "Start refused: $($Preflight.Status). No existing process was modified." }
# Other services require future explicit runtime validation and isolated envs.
# Stage 2 validates only the native LLM. Fail closed instead of routing requests
# to an original STT/TTS/WS still listening on the legacy fixed ports.
if ($Service -ne 'llm') { throw 'Non-LLM runtime launch disabled in Stage 2 pending isolated dependency and dependency-owner validation.' }

$Existing = Read-OwnedProcess
if ($Existing -and $Existing.Info) { throw 'Owned service already running; duplicate start refused' }
if (Test-Path -LiteralPath $RecordPath) { throw 'Stale owner record requires inspection; refusing overwrite' }
$SerializedArgs = foreach ($Arg in $LaunchArgs) {
    if ($Arg.Contains('"')) { throw 'Embedded quote in launch argument is unsupported' }
    '"'+$Arg+'"'
}
$Process = Start-Process -FilePath $Program -ArgumentList ($SerializedArgs -join ' ') -WorkingDirectory $Workspace -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr -WindowStyle Hidden -PassThru
try {
    $Info = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)" -ErrorAction Stop
    if (-not $Info -or $Info.ExecutablePath -ne $Program) { throw 'Cannot verify newly created process' }
    $NewOwner=[ordered]@{Workspace=$Workspace;Key=$Key;ProcessId=$Process.Id;Executable=$Program;Arguments=($LaunchArgs -join "`n");CommandLine=$Info.CommandLine;CreatedUtc=$Info.CreationDate.ToUniversalTime().ToString('o');StackRunId=$env:REBUILD_STACK_RUN_ID}
    $NewOwner.Profile=$Profile;$NewOwner.ModelPath=$Llm.model;$NewOwner.ModelAlias=$Llm.alias;$NewOwner.ModelSHA256=$ModelHash
    if ($IsHybrid) { $NewOwner.BinarySHA256=$HybridBinarySHA256; $NewOwner.RuntimeManifestSHA256=$Llm.runtime_manifest_sha256 }
    $NewOwner | ConvertTo-Json | Set-Content -LiteralPath $RecordPath -Encoding utf8
    $Deadline = [DateTime]::UtcNow.AddSeconds(180)
    $Ready = $false
    while ([DateTime]::UtcNow -lt $Deadline) {
        $Process.Refresh()
        if ($Process.HasExited) { break }
        if ($Service -eq 'llm') { Register-LlmConsoleChildren }
        $Binding = @(Get-Listeners)
        if ($Binding.Count -and @($Binding | Where-Object {$_.OwningProcess -ne $Process.Id -or $_.LocalAddress -ne '127.0.0.1'}).Count) { throw 'Unexpected listener owner or address' }
        try { $Response=Invoke-RestMethod -Uri $Health -TimeoutSec 3; if ($Response.status -eq 'ok' -and $Binding.Count) { $Ready=$true; break } } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $Ready) { throw 'Owned LLM did not become ready' }
    Assert-ActiveModelResponse (Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 3)
    $Process.Refresh()
    [ordered]@{Status='READY';Pid=$Process.Id;WorkingSetBytes=$Process.WorkingSet64;Endpoint=$Health;Profile=$Profile;GPUOffload=$GpuLayers;Context=4096;ParallelSlots=1;GpuOffloadIsConfigurationOnly=$true} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Runtime 'startup.json') -Encoding utf8
    Write-Output "Rebuild LLM ready on $Health"
} catch {
    # Cleanup is restricted to the Process object just returned by Start-Process,
    # or the identity-verified owner record. Never a name/port based kill.
    if (Test-Path -LiteralPath $RecordPath) { Stop-OwnedProcess }
    elseif (-not $Process.HasExited) { throw 'Launch failed before trustworthy owner was saved; process preserved for identity-based recovery' }
    throw
}
