# Redacted coding-agent development record

These are faithful, condensed excerpts from the actual development conversation and
observed command results. They are not a full raw transcript. Secrets, account details,
user chat contents, and local identity paths are intentionally omitted.

## User constraints

- “except GitHub” — keep development local; college Wi-Fi blocks GitHub access.
- “I can't switch networks now” — no mobile-hotspot workaround available.
- “don't do check the tests, just work on it” — suite execution deferred.
- Re-read Task.pdf, identify pending work, and continue implementation autonomously.

## Observed failures and corrections

1. GitHub downloads reset on the college network. Implemented a jsDelivr transcript
   downloader with advertised SHA-256 validation. Result: 303 transcripts downloaded;
   ingestion recorded 34,265 passages. Original repository references were retained.
2. System Node 22.16 was below Pi's supported engine. Used available Node 24.19 runtime;
   launcher checks >=22.19 and accepts an explicit NodePath.
3. Dependency downloads initially timed out, including a pip file-lock failure.
   Retried with longer network timeout; Python dependencies installed. npm installation
   used a mirror with lockfile integrity and disabled lifecycle scripts.
4. Ollama image/model were not initially installed. Docker image and qwen3:4b downloaded;
   local hello completed after a cold start. Subsequent local QA responses were observed
   at approximately 153 and 193 seconds. The app must not promise instant generation.
5. Cloud jobs failed despite a saved key. A direct Google generation request returned
   HTTP 401 UNAUTHENTICATED / ACCESS_TOKEN_TYPE_UNSUPPORTED. A bearer diagnostic also
   returned 401 / API_KEY_SERVICE_BLOCKED. Credential values and full bodies are omitted.
   Cloud remains blocked; a saved key is no longer displayed as a verified connection.
6. Audit found cancellation could still save an in-flight answer and cancelled jobs
   could keep polling. Added a pre-save cancellation boundary and terminal UI state.
7. PowerShell model-list matching treated an array as a condition. Joined output before
   checking the configured model to avoid unnecessary repeat downloads.
8. Agent timeout was capped below the user's configured backend timeout. Raised bridge
   cap to 1,200 seconds and retained per-request deadlines.

## Handoff work

Created README, design/architecture documents, requirement audit, meaningful test sources,
manual acceptance plan, camera-on demo script, and an allowlisted source ZIP packager.
No GitHub push, YouTube upload, or submission form action was performed. Automated tests
were not run per user instruction. Clean-machine Docker and full product acceptance
remain explicitly unverified rather than labelled passed.

## Exact sanitized command/output excerpts from final handoff

```text
> .\start.ps1
Container lenny-growth-assistant-ollama-1 Running
{"changed": 0, "discovered": 303, "episodes": 303, "chunks": 34265}
Starting The Lenny Growth Assistant at http://127.0.0.1:8000

> GET /api/status
{"database": true, "agent": true, "ollama": true, "gemini": true,
 "gemini_state": "unverified", "episodes": 303, "chunks": 34265}

> Direct Gemini authentication diagnostic (credential omitted)
bearer 401 UNAUTHENTICATED ['API_KEY_SERVICE_BLOCKED']
api-key 401 UNAUTHENTICATED ['ACCESS_TOKEN_TYPE_UNSUPPORTED']

> Google AI Studio API Keys page
Network error, try again.
```

Here `gemini: true` means a key is configured, not verified working cloud generation.
No automated test command was executed. A documentation update initially hit Windows
cp1252 decoding of Unicode punctuation; using explicit UTF-8 corrected the write.

## Grounding issue found in the local document example

A real local Markdown generation completed in 258.5 seconds and persisted an artifact.
The draft repeated a negation error from an internally contradictory transcript passage
about the Sean Ellis survey. A second excerpt clearly discussed very-disappointed users.
This showed that valid citation IDs alone were inadequate. The example was manually
corrected with explicit provenance and the ambiguous numeric threshold omitted. Added a
separate strict model evidence-review pass and rejection on any verdict other than exact
SUPPORTED. The new review pass has not been exercised end-to-end; it remains fallible
and adds latency. This was a real development finding, not a claimed passing test.

## Cloud recovery follow-up

AI Studio loaded successfully on retry. A newer key already present in the same
project was copied directly into private configuration; it was never printed.
The replacement authenticated, but Gemini 2.5 Flash returned HTTP 404: unavailable
to new users. The API directed this account to Gemini 3.8 Flash, which returned 200.
Updated configured/default model to 3.8 Flash. Real Pi cloud QA and its evidence
review completed. Longer responses sometimes failed with fetch errors or
“Incomplete JSON segment at the end”; these now receive bounded transient retries.
Temporary provider-body diagnostics were removed after diagnosis.

## Longer outputs and free-tier limit

Incomplete streamed JSON responses were classified as transient network errors.
With bounded retries, four essay sections and the evidence review completed,
producing a 1,190-word Markdown artifact. A subsequent HTML request returned a
quota error; the app exposed PROVIDER_QUOTA. No billing changes were made.
The HTML request was explicitly switched to local Ollama. The model review is
fallible: the essay contains interpretations that still merit human source review.

Local HTML inference completed after 241 seconds with empty output. Cloud HTML
remained quota-limited after cooldown. Added an explicit Markdown-to-HTML conversion
endpoint and viewer button; the 1,190-word essay was converted, stored, and exported.
This conversion introduces no new factual claims and is labelled in documentation.


## 12 October 2026 verification (redacted)

User authorized final tests and both-model checks. Docker/DB/API were reachable.
29 Python tests and 10 transport tests passed. Rebuilt both Docker images and
verified a disposable backend container against a temporary PostgreSQL schema.
The isolated bridge returned expected missing-key and invalid-provider errors.
Gemini completed QA, a follow-up and Markdown, but direct HTML failed during
review with NETWORK_ERROR and an essay failed in section 2 with MODEL_TIMEOUT.
Local QA and follow-up repeated a semantic mistake: disappointment without the
product was treated as evidence of a product flaw. Local HTML also invented a
>10% success threshold from an interviewer example. The model reviewer accepted
these mistakes; the local Markdown draft was rejected instead. This distinguishes
job completion from factual correctness. Full final results: verification.md.
No credentials, confidential PDF, raw provider payloads or private runtime logs
are included in this handoff log. No GitHub publication or billing changes.

Final local essay attempt failed with OUTPUT_TRUNCATED during source review after about nine minutes. Both providers' unsupported requests abstained without calling a model. Browser Source/Copy and rendering worked; download remains unverified. Swagger /docs is blank because its external and inline scripts conflict with CSP; /openapi.json works. The full results are recorded without treating completed jobs as automatic passes.

## Reference-demo implementation and reliability follow-up

Compared the supplied demo transcript with Task.pdf and the actual stack. Added
persistent dark mode, PostgreSQL saved insights, Discover starters and essay audience.
Added an ownership-checked server download endpoint; the browser successfully saved
Research-document.md. Replaced blank Swagger with a script-free API reference.
Reindexed conflicting upstream guest/title metadata with a warning and no video link.
Added survey-condition/threshold regression guards and one short-draft correction.
Removed prior assistant prose from generation context to avoid repeating old errors.
Added essay length editing and bounded section review. A long non-streaming local
revision encountered a NETWORK_ERROR at about five minutes: changed Ollama transport
to consume NDJSON incrementally, with split-UTF8 and interrupted-stream tests. Gemini
answered after restart but then returned PROVIDER_QUOTA; no billing/key changes.
Final live outcomes are recorded in verification.md. Reference-demo differences and
remaining publication actions are recorded in transcript-review.md and demo.md.

## Final verification — 12 October 2026

Completed the 20 supported / 5 unsupported Ollama baseline. Results were 6 supported
answers marked cited, 6 insufficient, 8 rejected, and all 5 unsupported prompts
abstained. Corrected the Alex Hardiman ingest typo and confirmed repeat ingestion was
idempotent. Post-fix answer, follow-up, Markdown and HTML checks passed their app
evidence/citation gates. The latest essay run took 701.6 seconds and was rejected after
two section corrections; no verified essay artifact was saved. Gemini follow-ups
remain blocked by provider quota. Final automated checks passed: 50 Python tests, 10
Node transport tests and Python compileall. Updated verification and requirement docs
and rebuilt a 57-file source-only ZIP. No GitHub push, recording or form submission
was performed.
