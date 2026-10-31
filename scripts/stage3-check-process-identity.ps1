# Deterministic tests of the actual manager functions; no real process APIs.
$ErrorActionPreference = 'Stop'
$Workspace = Split-Path $PSScriptRoot -Parent
$Tokens=$null; $ParseErrors=$null
$Tree=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'rebuild-service.ps1'),[ref]$Tokens,[ref]$ParseErrors)
if (@($ParseErrors).Count) { throw 'Manager syntax error' }
foreach ($Name in @('ConvertTo-RebuildUtcTicks','Read-OwnedProcess')) {
    $Function=$Tree.Find({param($Node) $Node -is [Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq $Name},$true)
    if (-not $Function) {throw "Function missing: $Name"}
    . ([ScriptBlock]::Create($Function.Extent.Text))
}
$TestDir=Join-Path $Workspace 'runtime\stage3\process-identity-tests'
[IO.Directory]::CreateDirectory($TestDir) | Out-Null
$RecordPath=Join-Path $TestDir 'mock-owner.json'
$Key='llm-4b'
$Program='D:\CyberGirlfriend\tools\llama.cpp\llama-server.exe'
$LaunchArgs=@('-m','mock-model','--port','8081')
$Utc=[DateTimeOffset]::Parse('2026-10-23T00:14:15.4237640Z')
$Results=[Collections.Generic.List[string]]::new()
function Get-CimInstance { param($ClassName,$Filter,$ErrorAction) return $script:MockInfo }
function Reset-MockOwner {
    $script:MockInfo=[pscustomobject]@{ProcessId=900001;ExecutablePath=$Program;CommandLine='mock-exact-command';CreationDate=$Utc.UtcDateTime}
    $script:MockRecord=[ordered]@{Workspace=$Workspace;Key=$Key;ProcessId=900001;Executable=$Program;Arguments=($LaunchArgs -join "`n");CommandLine='mock-exact-command';CreatedUtc=$Utc.ToString('o')}
}
function Save-MockOwner { $script:MockRecord | ConvertTo-Json | Set-Content -LiteralPath $RecordPath -Encoding utf8 }
function Assert-MockAccepted([string]$Name) {
    Save-MockOwner
    $Result=Read-OwnedProcess
    if ($Result.Info.ProcessId -ne 900001) {throw "Expected acceptance: $Name"}
    $Results.Add("PASS: $Name")
}
function Assert-MockRejected([string]$Name) {
    Save-MockOwner
    $Rejected=$false
    try { Read-OwnedProcess | Out-Null } catch { $Rejected=$true }
    if (-not $Rejected) {throw "Expected refusal: $Name"}
    $Results.Add("PASS: $Name")
}
Reset-MockOwner
Assert-MockAccepted 'JSON round-trip creation time accepted by actual Read-OwnedProcess'
foreach ($Value in @('2026-10-23T00:14:15.423764Z','2026-10-22T17:14:15.4237640-07:00',$Utc,$Utc.UtcDateTime,$Utc.LocalDateTime)) {
    if ((ConvertTo-RebuildUtcTicks $Value) -ne $Utc.UtcDateTime.Ticks) {throw 'UTC normalization mismatch'}
}
$Results.Add('PASS: strings (6/7 fractions), offset strings, DateTimeOffset, UTC/local DateTime normalize identically')
foreach ($Case in @('wrong-date','one-tick','wrong-pid','wrong-executable','wrong-command','foreign-workspace','wrong-arguments','malformed-time')) {
    Reset-MockOwner
    switch ($Case) {
        'wrong-date' {$script:MockRecord.CreatedUtc=$Utc.AddSeconds(1).ToString('o')}
        'one-tick' {$script:MockRecord.CreatedUtc=$Utc.AddTicks(1).ToString('o')}
        'wrong-pid' {$script:MockInfo.ProcessId=900002}
        'wrong-executable' {$script:MockInfo.ExecutablePath='D:\foreign.exe'}
        'wrong-command' {$script:MockInfo.CommandLine='different-command'}
        'foreign-workspace' {$script:MockRecord.Workspace='D:\CyberGirlfriend'}
        'wrong-arguments' {$script:MockRecord.Arguments='different-arguments'}
        'malformed-time' {$script:MockRecord.CreatedUtc='not-a-timestamp'}
    }
    Assert-MockRejected $Case
}
foreach ($Value in @('2026-10-23T00:14:15.4237640', [DateTime]::SpecifyKind($Utc.DateTime,[DateTimeKind]::Unspecified), $null)) {
    $Rejected=$false
    try {ConvertTo-RebuildUtcTicks $Value | Out-Null} catch {$Rejected=$true}
    if (-not $Rejected) {throw 'Ambiguous/missing timestamp accepted'}
}
$Results.Add('PASS: missing/unspecified timezones and null rejected')
Remove-Item -LiteralPath $RecordPath
@{Status='PASS';IsMock=$true;RealProcessOperations=0;Precision='Exact 100 ns UTC ticks; no tolerance';Checks=@($Results)} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Workspace 'runtime\stage3\process-identity-checks.json') -Encoding utf8
$Results
