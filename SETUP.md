# Setup

The implementation is now present. Use [README.md](README.md) for current instructions.

- On this configured laptop: start Docker Desktop and run `.\start.ps1`.
- Open http://127.0.0.1:8000 and select Local Ollama.
- Qwen3 4B is downloaded; PostgreSQL and the Pi bridge are configured.
- Corpus: 303 episodes, 34,265 passages at the last observed import.
- Gemini now uses a working private replacement key and Gemini 3.8 Flash.
- Fresh Docker installation: `.\bootstrap.ps1 -Gpu -UseCdn`; see README limitations.
- Stop: `.\stop.ps1`. Data and model files are preserved.

The laptop deployment uses D:\AI\OllamaModels, an existing PostgreSQL container on
port 55432, Python in `.venv`, and a supported Node runtime. The portable Docker
setup uses its own named volumes instead of relying on those laptop paths.
