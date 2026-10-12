#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
mkdir -p data/transcripts
docker compose up -d --build
task_model=$(docker compose exec -T app python -c 'from backend.config import OLLAMA_MODEL; print(OLLAMA_MODEL)')
docker compose exec -T ollama ollama pull "$task_model"
docker compose exec -T app python -m scripts.download_transcripts || docker compose exec -T app python -m scripts.download_cdn
docker compose exec -T app python -m scripts.ingest
printf '%s\n' 'Ready: http://127.0.0.1:8000'
