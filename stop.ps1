$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
# Match only processes serving this project's two local ports and source commands.
foreach ($taskPort in @(8000,8787)) {
    $taskListeners=Get-NetTCPConnection -LocalPort $taskPort -State Listen -ErrorAction SilentlyContinue
    foreach ($taskListener in $taskListeners) {
        $taskProcess=Get-CimInstance Win32_Process -Filter "ProcessId=$($taskListener.OwningProcess)"
        if ($taskProcess.CommandLine -match 'backend\.main:app|agent[/\\]server\.mjs') {
            Stop-Process -Id $taskProcess.ProcessId
        } else { Write-Warning "Port $taskPort belongs to another process; left it running." }
    }
}
docker compose -f compose.ollama.yaml stop
docker stop lenny-postgres
Write-Output 'Local services stopped. Conversations, transcripts, and models are preserved.'

