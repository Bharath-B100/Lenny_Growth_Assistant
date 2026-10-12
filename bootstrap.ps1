param([switch]$Gpu,[switch]$UseCdn)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
New-Item -ItemType Directory -Force -Path 'data\transcripts' | Out-Null
$taskCompose=@('-f','compose.yaml')
if ($Gpu) { $taskCompose+=@('-f','compose.gpu.yaml') }
docker compose @taskCompose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Container build/start failed.' }
$taskModel=(docker compose @taskCompose exec -T app python -c "from backend.config import OLLAMA_MODEL; print(OLLAMA_MODEL)").Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not read configured model.' }
docker compose @taskCompose exec -T ollama ollama pull $taskModel
if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
$taskDownload=if($UseCdn){'scripts.download_cdn'}else{'scripts.download_transcripts'}
docker compose @taskCompose exec -T app python -m $taskDownload
if ($LASTEXITCODE -ne 0) { throw 'Transcript download failed. Try -UseCdn if GitHub downloads are blocked.' }
docker compose @taskCompose exec -T app python -m scripts.ingest
if ($LASTEXITCODE -ne 0) { throw 'Ingestion failed.' }
Write-Output 'Ready: http://127.0.0.1:8000'

