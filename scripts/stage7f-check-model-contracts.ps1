$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'rebuild-process-identity.ps1')
$Tokens=$null;$Errors=$null
$Ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'rebuild-service.ps1'),[ref]$Tokens,[ref]$Errors)
if($Errors.Count){throw ($Errors | Out-String)}
$Node=$Ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Assert-ActiveModelResponse'},$true)
Invoke-Expression $Node.Extent.Text
$Llm=[pscustomobject]@{alias='cybergirlfriend-qwen3-1.7b-rebuild'}
$Body=[pscustomobject]@{data=@([pscustomobject]@{id=$Llm.alias;meta=[pscustomobject]@{n_ctx=4096;n_params=2031739904}})}
Assert-ActiveModelResponse $Body
$Results=@('active alias and 4096 context accepted')
foreach($Case in @('alias','context','parameters')){
    $Bad=$Body | ConvertTo-Json -Depth 5 | ConvertFrom-Json
    switch($Case){'alias'{$Bad.data[0].id='wrong'};'context'{$Bad.data[0].meta.n_ctx=2048};'parameters'{$Bad.data[0].meta.n_params=0}}
    $Rejected=$false;try{Assert-ActiveModelResponse $Bad}catch{$Rejected=$true}
    if(-not $Rejected){throw "Bad model response accepted: $Case"}
    $Results+="reject invalid $Case"
}
$Root=[pscustomobject]@{Pid=101;ParentPid=100;Exe='verified-server';CommandLine='exact';CreationFiletime=[long]100001}
$Exe=Join-Path ([Environment]::GetFolderPath('System')) conhost.exe
$Child=[pscustomobject]@{Pid=102;ParentPid=101;Exe=$Exe;CommandLine=('\??\'+$Exe+' 0x4');CreationFiletime=[long]100002}
Assert-RebuildConsoleIdentity $Child $Child $Root $Root
$Bad=$Child.PSObject.Copy();$Bad.CreationFiletime++
$Rejected=$false;try{Assert-RebuildConsoleIdentity $Child $Bad $Root $Root}catch{$Rejected=$true}
if(-not $Rejected){throw 'Console FILETIME mutation accepted'}
$Results+='existing exact conhost/FILETIME protection retained'
$Results+='PowerShell syntax PASS'
$Results | ConvertTo-Json
