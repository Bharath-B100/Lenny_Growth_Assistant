import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://lenny:lenny_local@127.0.0.1:55432/lenny')
OLLAMA_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3:4b-instruct-2507-q4_K_M')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')
BRIDGE_URL = os.getenv('AGENT_BRIDGE_URL', 'http://127.0.0.1:8787')
DATA_DIR = Path(os.getenv('TRANSCRIPTS_DIR', str(ROOT / 'data' / 'transcripts')))
MODEL_TIMEOUT = int(os.getenv('MODEL_TIMEOUT_SECONDS', '900'))
DEFAULT_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')
