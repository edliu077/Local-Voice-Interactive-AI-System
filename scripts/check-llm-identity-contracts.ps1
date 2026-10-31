$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'rebuild-process-identity.ps1')
$Exe=Join-Path ([Environment]::GetFolderPath('System')) 'conhost.exe'
$Root=[pscustomobject]@{Pid=101;ParentPid=100;Exe='D:\resource\llama-server.exe';CommandLine='exact model arguments';CreationFiletime=[long]10000001}
$Child=[pscustomobject]@{Pid=102;ParentPid=101;Exe=$Exe;CommandLine=('\??\'+$Exe+' 0x4');CreationFiletime=[long]10000002}
$Results=[Collections.Generic.List[string]]::new()
Assert-RebuildConsoleIdentity $Child $Child $Root $Root
$Results.Add('exact registered conhost accepted')
$Other=$Child.PSObject.Copy();$Other.CommandLine='\??\'+$Exe+' 0xffffffff -ForceV1'
Assert-RebuildConsoleIdentity $Other $Other $Root $Root
$Results.Add('exact registered ForceV1 conhost accepted')
foreach($Field in @('Pid','ParentPid','Exe','CommandLine','CreationFiletime')) {
    $Bad=$Child.PSObject.Copy()
    switch($Field){
        'Pid' {$Bad.Pid++};'ParentPid' {$Bad.ParentPid++};'Exe' {$Bad.Exe='D:\fake\conhost.exe'}
        'CommandLine' {$Bad.CommandLine+=' unknown'};'CreationFiletime' {$Bad.CreationFiletime++}
    }
    $Rejected=$false
    try {Assert-RebuildConsoleIdentity $Child $Bad $Root $Root} catch {$Rejected=$true}
    if(-not $Rejected){throw "Unsafe accepted mutation: $Field"}
    $Results.Add("reject changed $Field")
}
$Rejected=$false
try {Assert-RebuildConsoleIdentity $Child $Other $Root $Root} catch {$Rejected=$true}
if(-not $Rejected){throw 'Unrecorded command transition accepted'}
$Results.Add('unrecorded command transition rejected')
$BadRoot=$Root.PSObject.Copy();$BadRoot.CreationFiletime++
$Rejected=$false
try {Assert-RebuildConsoleIdentity $Child $Child $Root $BadRoot} catch {$Rejected=$true}
if(-not $Rejected){throw 'Root reuse accepted'}
$Results.Add('root FILETIME reuse rejected')
$Rejected=$false
try {Assert-RebuildConsoleIdentity $null $Child $Root $Root} catch {$Rejected=$true}
if(-not $Rejected){throw 'Unknown child accepted'}
$Results.Add('unknown child rejected')
# Exercise the actual stop/failed-start cleanup function with fake process data.
# Only function definitions are loaded; the management script main body never runs.
$Tokens=$null;$Errors=$null
$Ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'rebuild-service.ps1'),[ref]$Tokens,[ref]$Errors)
foreach($Name in @('Stop-OwnedProcess','Stop-OwnedProcessChecked','Stop-LlmOwnedTree')) {
    $Node=$Ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name},$true)
    Invoke-Expression $Node.Extent.Text
}
$Workspace=Split-Path $PSScriptRoot -Parent;$Service='llm';$Action='stop';$RecoveryEvidence=$null
$Runtime=Join-Path $Workspace ('runtime\stage7c-recovery\stop-contracts-'+[Guid]::NewGuid().ToString('N'))
$null=New-Item -ItemType Directory -Path $Runtime
$RecordPath=Join-Path $Runtime 'owner.json'
function Assert-OwnedPath($Path) {if(-not $Path.StartsWith($Runtime+'\')){throw 'Test output escaped'}}
function Read-OwnedProcess {return $script:MockOwned}
function Get-RebuildIdentity($Info) {return $Info.Identity}
function Get-Listeners {return $script:MockListeners}
function Get-CimInstance {param($ClassName,$Filter,$ErrorAction)
    if($Filter -like '*ParentProcessId = 102*'){return @()}
    if($Filter -like '*ParentProcessId = 101*'){return $script:MockChild}
    return @($script:MockOwned.Info,$script:MockChild)
}
function Get-Process {param($Id,$ErrorAction) return $null}
$Info=[pscustomobject]@{ProcessId=101;Identity=$Root}
$Record=[pscustomobject]@{ProcessId=101;ConsoleRootIdentity=$Root;ConsoleChildren=@($Child)}
$script:MockOwned=[pscustomobject]@{Info=$Info;Record=$Record};$script:MockListeners=@()
try {
    foreach($Case in @('unknown','time','command','parent')) {
        $Actual=$Child.PSObject.Copy()
        switch($Case){'unknown'{$Actual.Pid=999};'time'{$Actual.CreationFiletime++};'command'{$Actual.CommandLine+=' unknown'};'parent'{$Actual.ParentPid=999}}
        $script:MockChild=[pscustomobject]@{ProcessId=$Actual.Pid;ParentProcessId=$Actual.ParentPid;Identity=$Actual}
        'original-evidence' | Set-Content -LiteralPath $RecordPath
        $Rejected=$false
        try{Stop-OwnedProcess}catch{$Rejected=$true}
        if(-not $Rejected -or (Get-Content $RecordPath -Raw).Trim() -cne 'original-evidence'){throw "Stop did not preserve conflict: $Case"}
        $Results.Add("actual stop rejects $Case and preserves owner/audit")
    }
    if(@(Get-ChildItem $Runtime -Filter 'identity-conflict-*.json').Count -ne 4){throw 'Conflict audit missing'}
    $script:MockOwned.Info=$null
    $script:MockListeners=@([pscustomobject]@{LocalPort=8081;OwningProcess=999})
    $Rejected=$false
    try{Stop-OwnedProcess}catch{$Rejected=$true}
    if(-not $Rejected -or -not (Test-Path $RecordPath)){throw 'Occupied port archive accepted'}
    $Results.Add('absent root with occupied port refuses owner archival')
    $script:MockListeners=@()
    $null=Stop-OwnedProcess
    if(Test-Path $RecordPath){throw 'Proven absent processes were not archived'}
    $Results.Add('absent root/children and released port permit archive')
    if(-not ($Ast.Extent.Text -match 'if \(Test-Path -LiteralPath \$RecordPath\) \{ Stop-OwnedProcess \}')){throw 'Failed-start cleanup bypassed checked stop'}
    $Results.Add('normal stop and failed-start cleanup share checked stop')
} finally {
    # Preserve deterministic evidence; never touch a real service owner.
    $Results | ConvertTo-Json | Set-Content (Join-Path $Runtime 'results.json')
}
foreach($Path in @('rebuild-service.ps1','rebuild-process-identity.ps1','check-llm-identity-contracts.ps1')) {
    $Tokens=$null;$Errors=$null
    $null=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $Path),[ref]$Tokens,[ref]$Errors)
    if($Errors.Count){throw ($Errors | Out-String)}
}
$Results.Add('PowerShell syntax accepted')
$Results | ConvertTo-Json
