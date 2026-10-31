# Exact process snapshots shared by the LLM normal-stop and failed-start cleanup.
function Get-RebuildIdentity($Info) {
    $Process = [Diagnostics.Process]::GetProcessById([int]$Info.ProcessId)
    try {
        [pscustomobject]@{Pid=[int]$Info.ProcessId;ParentPid=[int]$Info.ParentProcessId;
            Exe=[string]$Info.ExecutablePath;CommandLine=[string]$Info.CommandLine;
            CreationFiletime=$Process.StartTime.ToUniversalTime().ToFileTimeUtc()}
    } finally { $Process.Dispose() }
}

function Assert-RebuildExactIdentity($Expected, $Actual) {
    if (-not $Expected -or -not $Actual -or
        $Expected.Pid -ne $Actual.Pid -or $Expected.ParentPid -ne $Actual.ParentPid -or
        $Expected.CreationFiletime -ne $Actual.CreationFiletime -or
        -not [string]::Equals($Expected.Exe,$Actual.Exe,[StringComparison]::OrdinalIgnoreCase) -or
        $Expected.CommandLine -cne $Actual.CommandLine) { throw 'Exact process identity conflict' }
}

function Assert-RebuildConsoleShape($Child, $Root) {
    $Exe = Join-Path ([Environment]::GetFolderPath('System')) 'conhost.exe'
    $Prefix = '\??\' + $Exe
    # Complete command lines, not substring or executable-name matching.
    $Allowed = @(($Prefix+' 0x4'), ($Prefix+' 0xffffffff -ForceV1'))
    $CommandAllowed = $false
    foreach ($Command in $Allowed) {
        # Only the executable spelling is case insensitive. Arguments are exact.
        $Arg = $Command.Substring($Prefix.Length)
        if ($Child.CommandLine.Length -eq $Command.Length -and
            $Child.CommandLine.Substring($Prefix.Length) -ceq $Arg -and
            [string]::Equals($Child.CommandLine.Substring(0,$Prefix.Length),$Prefix,[StringComparison]::OrdinalIgnoreCase)) { $CommandAllowed=$true }
    }
    if (-not [string]::Equals($Child.Exe,$Exe,[StringComparison]::OrdinalIgnoreCase) -or
        $Child.ParentPid -ne $Root.Pid -or $Child.Pid -eq $Root.Pid -or
        $Child.CreationFiletime -lt $Root.CreationFiletime -or -not $CommandAllowed) {
        throw 'Unverified console child'
    }
}

function Assert-RebuildConsoleIdentity($Expected, $Actual, $ExpectedRoot, $ActualRoot) {
    Assert-RebuildExactIdentity $ExpectedRoot $ActualRoot
    Assert-RebuildConsoleShape $Actual $ActualRoot
    Assert-RebuildExactIdentity $Expected $Actual
}
