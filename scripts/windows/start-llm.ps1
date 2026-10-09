#requires -Version 5.1
. (Join-Path $PSScriptRoot 'common.ps1')

$HostAddress = Get-LviaiLoopbackHost 'LVIAI_LLM_HOST'
$Port = Get-LviaiPort 'LVIAI_LLM_PORT' 8080
$Server = Require-LviaiFile (Get-LviaiPath 'LVIAI_LLAMA_SERVER' (Join-Path $script:LviaiProjectRoot 'tools\llama.cpp\llama-server.exe')) 'llama.cpp server'
$Model = Require-LviaiFile (Get-LviaiPath 'LVIAI_LLM_MODEL' (Join-Path $script:LviaiProjectRoot 'models\llm\qwen3-1.7b-q4_k_m\Qwen3-1.7B-Q4_K_M.gguf')) 'Qwen3-1.7B GGUF'
$Arguments = @('-m', $Model, '--host', $HostAddress, '--port', "$Port", '-ngl', '0', '-c', '4096', '-t', '10', '-tb', '12', '-np', '1', '--alias', 'lviai-qwen3', '--reasoning', 'off')
$Deadline = [DateTime]::UtcNow.AddSeconds(120)
$Started = Start-LviaiLoggedProcess 'llm' $Server $Arguments $script:LviaiProjectRoot $HostAddress $Port @([System.IO.Path]::GetFileName($Server), 'lviai-qwen3') 120
$Remaining = [Math]::Max(1, [int][Math]::Ceiling(($Deadline - [DateTime]::UtcNow).TotalSeconds))
Wait-LviaiJsonHealth 'llm' "http://${HostAddress}:$Port/health" 'ok' $Remaining $Started.Stdout $Started.Stderr
