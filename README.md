# The Lenny Growth Assistant

A local research app that turns Lenny's Podcast transcripts into cited answers,
follow-up conversations, approximately 1,250-word essays, and Markdown/HTML artifacts.
FastAPI + PostgreSQL + Pi Coding Agent SDK + Ollama, with optional Gemini.

Includes persistent dark mode, saved insights, Discover topic starters, and an essay
audience field. See [reference demo comparison](docs/transcript-review.md).

## Start on this laptop

Open PowerShell in this folder, start Docker Desktop, then run:

```powershell
.\start.ps1
```

Open http://127.0.0.1:8000. Select **Local Ollama**, ask a product/growth question,
and inspect the source chips. Select Essay, Markdown, or HTML for an artifact.
The library currently contains 303 episodes and 34,265 overlapping passages.
The first request warms the model; local answers observed during development took
roughly 2–3 minutes. A four-section essay can take substantially longer.

Stop without deleting conversations or models:

```powershell
.\stop.ps1
```

## Fresh machine: one-command Docker setup

Requires Docker Compose, internet access, sufficient disk space for images/model,
and about 16 GB RAM. CPU inference works but is slow; NVIDIA GPU is optional.
Do not run this alongside the laptop launcher: both use port 8000 and the same
Compose project name. The portable deployment has separate database/model volumes.

```powershell
.\bootstrap.ps1 -Gpu -UseCdn
```

Omit `-Gpu` on systems without a supported NVIDIA GPU. `-UseCdn` downloads the
specified transcript repository through jsDelivr with hash verification when GitHub
is inaccessible. Linux/macOS: `sh bootstrap.sh` (CPU by default). First setup takes
longer because dependencies, model, and transcripts must download.
The portable clean-machine workflow is supplied but has not been executed end-to-end.

## Configuration

The launchers create `.env` from `.env.example` if missing. Keep `.env` private.

| Setting | Purpose |
|---|---|
| `LLM_PROVIDER` | Default deployment provider; browser remembers its selection |
| `OLLAMA_MODEL` | Local model, default `qwen3:4b-instruct-2507-q4_K_M` |
| `OLLAMA_BASE_URL` | Local Ollama endpoint |
| `GEMINI_API_KEY` | Optional server-only Google credential |
| `GEMINI_MODEL` | Cloud model ID, default `gemini-3.8-flash` |
| `MODEL_TIMEOUT_SECONDS` | Per-section generation timeout; increase for slow hardware |
| `DATABASE_URL` | PostgreSQL connection string |
| `AGENT_BRIDGE_URL` | Private Pi bridge endpoint |

Restart the services after editing configuration. Selecting the provider in the UI
changes subsequent requests without code edits. **There is no automatic cloud
fallback.** A failure is shown; choose Local Ollama and resend to stay local.
A configured key is not proof that Google accepts it. On this machine, a working replacement key and Gemini 3.8 Flash have now produced
a source-backed answer through Pi. Older Gemini 2.5 Flash was unavailable to this account.
Interrupted network/JSON-stream responses receive up to two retries.
Do not enable paid billing merely to troubleshoot authentication.

For the non-container laptop launcher: Python 3.13 and Node >=22.19 are required.
`start.ps1 -Setup` installs pinned dependencies. It prefers the bundled Node runtime
when present. `-NodePath` selects another supported Node executable.
The checked-in npm lock uses registry.npmmirror.com URLs, installed during a college
network outage; integrity hashes remain in the lock. Change registry/lock deliberately
if your environment requires npmjs.org. Never disable certificate validation.

## How it works

1. Ingestion splits transcripts into overlapping passages and stores metadata and
   PostgreSQL full-text search vectors.
2. Retrieval selects up to six passages, combining a follow-up with prior user context.
3. A bounded Pi session generates from evidence with no shell or filesystem tools.
4. Citation IDs and a separate model evidence review gate drafts; replies, sources, sessions, jobs, and artifacts persist.
5. HTML is sanitized and displayed in a sandboxed iframe with restrictive CSP.

Citation-ID checks and a second model review do not prove every claim is supported. Review the excerpt cards.
Lexical retrieval can miss paraphrases or rank introductory passages too highly.
Small local models can produce uneven essays; out-of-range word counts show a warning.

## Useful endpoints and files

- `/api/status`: database, transcript counts, model/configuration status.
- `/health/live`, `/health/ready`: service liveness and database readiness.
- `/docs`: FastAPI API reference.
- `logs/`: local runtime logs; excluded from sharing.
- `PRD.md`, `design.md`, `architecture.md`: product and implementation decisions.
- `REQUIREMENTS.md`: evidence and remaining submission gaps.
- `docs/agent-log.md`: redacted development transcript excerpts, including failures.
- `docs/manual-test-plan.md`: manual acceptance plan, not a claim it passed.
- `docs/demo.md`: 2–3 minute camera-on recording script.
- `docs/examples.md`: provenance and limitations of the saved examples.

## Tests and verification status

On 12 October 2026, **51 Python tests and 10 Node transport tests passed**; Python
compile checks also passed. See [verification.md](docs/verification.md) for the live
model results and remaining acceptance work.
The Python run included real PostgreSQL checks in isolated temporary schemas.
Run from this folder:

```powershell
$env:LENNY_INTEGRATION='1'
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/native-transport.test.mjs
```

Opt-in real-provider checks: `python -m scripts.verify_live --provider ollama --essay`
or `--provider gemini`. These create labelled QA chats and use your existing model
configuration. Generated content remains fallible. See [verification.md](docs/verification.md)
for current real-model failures, browser results, and limits; test passes are not a
claim that all factual output or submission requirements are accepted.

## Troubleshooting

- Database unavailable: start Docker, rerun the launcher; restart app after database recovery.
- Local model missing: `docker compose -f compose.ollama.yaml exec -T ollama ollama pull qwen3:4b-instruct-2507-q4_K_M`.
- Timeout: shorten the question, increase timeout, or choose a smaller compatible model.
- Gemini 401/403: check the key's project, restrictions, and Gemini access in AI Studio;
  save a working credential privately and restart the agent. Never paste it into a chat.
- Gemini 429: wait for quota or explicitly choose Local Ollama.
- No evidence: name an episode/guest or ask a more specific supported question.
- Port conflict: stop this app's prior deployment; do not stop unrelated containers.
- Network failure: retry dependency downloads or use the documented transcript CDN route.
- Cancel: discards the reply at a stage boundary; the in-flight model call may keep running
  until it returns or times out. This can temporarily delay the next queued request.

## Deployment and data limits

This is a localhost single-user evaluation app. Browser UUIDs identify stored sessions;
they are not authentication. Do not expose it publicly without real authentication,
authorization, TLS, durable job workers, and rate limits. Only one API worker is supported.
Cloud selection sends the request, recent conversation, and excerpts to Google.
Local generation stays on the machine after installation/downloads.
The development database password is for localhost only.

Transcripts are fetched from https://github.com/ChatPRD/lennys-podcast-transcripts;
retain upstream attribution and review upstream terms before redistribution. The
assignment PDF, credentials, downloaded corpus, and unsanitized logs are not packaged.

## Source handoff without GitHub

```powershell
.\.venv\Scripts\python.exe scripts/package_source.py
```

This builds `deliverables/lenny-growth-assistant-source.zip` from an explicit source
allowlist. GitHub publication is deferred at the user's request. The evaluator also
requests a public repository, camera-on YouTube demo, and submission form: these are
still separate user handoff actions, not completed by creating a ZIP.

Saved Markdown documents also offer **Create HTML**: a styled source-preserving
conversion that needs no model call and remains available during cloud quota limits.
