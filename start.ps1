param([switch]$Setup,[switch]$RefreshTranscripts,[string]$NodePath='')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskRoot=$PSScriptRoot
$taskPython=Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskLogDir=Join-Path $taskRoot 'logs'
New-Item -ItemType Directory -Force -Path $taskLogDir | Out-Null
if (!(Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (!$NodePath) {
    $taskBundledNode=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
    if (Test-Path -LiteralPath $taskBundledNode) { $NodePath=$taskBundledNode }
    else { $NodePath=(Get-Command node -ErrorAction Stop).Source }
}
& $NodePath -e "const [a,b]=process.versions.node.split('.').map(Number); if(a<22 || (a===22&&b<19)) { console.error('Node 22.19+ is required. Install a newer Node or pass -NodePath.'); process.exit(1) }"
if ($LASTEXITCODE -ne 0) { throw 'Unsupported Node version.' }
docker info --format '{{.ServerVersion}}' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop and wait for its engine, then rerun this command.' }
docker compose -f compose.ollama.yaml up -d
if ($LASTEXITCODE -ne 0) { throw 'Ollama could not start. See README for GPU and port troubleshooting.' }
$taskDbExisting=docker ps -a --filter 'name=^lenny-postgres$' --format '{{.Names}}'
if ($taskDbExisting) { docker start lenny-postgres | Out-Null }
else {
    docker run -d --name lenny-postgres -e POSTGRES_USER=lenny -e POSTGRES_PASSWORD=lenny_local -e POSTGRES_DB=lenny -p 127.0.0.1:55432:5432 -v lenny-pgdata:/var/lib/postgresql/data postgres:17-bookworm | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL could not start.' }
}
if ($Setup -or !(Test-Path -LiteralPath $taskPython)) {
    if (!(Test-Path -LiteralPath $taskPython)) { python -m venv .venv }
    & $taskPython -m pip install -r backend/requirements-lock.txt --timeout 120
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}
if ($Setup -or !(Test-Path -LiteralPath 'agent\node_modules\@earendil-works\pi-coding-agent')) {
    Push-Location agent
    try { npm ci --ignore-scripts --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw 'Pi install failed. See README for the college-network mirror option.' } }
    finally { Pop-Location }
}
$taskModel=(& $taskPython -c "from backend.config import OLLAMA_MODEL; print(OLLAMA_MODEL)").Trim()
$taskModels=docker compose -f compose.ollama.yaml exec -T ollama ollama list
if (($taskModels -join "`n") -notmatch [regex]::Escape($taskModel)) {
    docker compose -f compose.ollama.yaml exec -T ollama ollama pull $taskModel
    if ($LASTEXITCODE -ne 0) { throw 'Local model download did not finish.' }
}
if ($RefreshTranscripts -or !(Test-Path -LiteralPath 'data\transcripts\manifest.json')) {
    & $taskPython -m scripts.download_transcripts
    if ($LASTEXITCODE -ne 0) { & $taskPython -m scripts.download_cdn }
    if ($LASTEXITCODE -ne 0) { throw 'Transcript download incomplete. Rerun -RefreshTranscripts or import files manually.' }
}
if ($RefreshTranscripts -and (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    throw 'Stop the app before refreshing ingestion, then rerun. Existing jobs must not be interrupted.'
}
$taskAppRunning=Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (!$taskAppRunning) {
    & $taskPython -m scripts.ingest
    if ($LASTEXITCODE -ne 0) { throw 'Transcript ingestion failed.' }
}
$taskPids=@{}
if (!(Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)) {
    $taskAgent=Start-Process -FilePath $NodePath -ArgumentList 'agent/server.mjs' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogDir 'agent.log') -RedirectStandardError (Join-Path $taskLogDir 'agent-error.log') -PassThru
    $taskPids.agent=$taskAgent.Id
}
if (!$taskAppRunning) {
    $taskApp=Start-Process -FilePath $taskPython -ArgumentList '-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogDir 'app.log') -RedirectStandardError (Join-Path $taskLogDir 'app-error.log') -PassThru
    $taskPids.app=$taskApp.Id
}
$taskPids | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskLogDir 'processes.json')
Write-Output 'Starting The Lenny Growth Assistant at http://127.0.0.1:8000'
Write-Output 'Model warm-up may take a few minutes. Service details: http://127.0.0.1:8000/api/status'
Write-Output 'Logs are in the project logs folder. Stop with .\stop.ps1 (data is preserved).'

