# The Lenny Growth Assistant

Status: implementation is present; see REQUIREMENTS.md for observed evidence and
remaining gaps. Acceptance criteria below remain targets, not passing test claims.

## User and problem

The primary user is a product manager or growth practitioner who needs to
turn advice from Lenny's Podcast into a source-backed answer, essay, or useful
document without manually searching long transcripts.

## Product outcomes

1. Ask a product or growth question and get a grounded answer with inspectable
   episode references and supporting excerpts.
2. Ask a follow-up while retaining context within the current chat.
3. Turn the evidence into an approximately 1,250-word essay through a dedicated
   writing skill derived from the supplied Ship 30 for 30 guide.
4. Generate Markdown or HTML/CSS and view it beside the conversation.

## Proposed measurable success criteria

- On a documented set of 20 representative questions, at least 90% of supported
  answers have citations whose excerpts support the main claims, checked manually.
- All five deliberately unsupported evaluation questions produce an explicit
  insufficient-evidence response instead of invented factual claims.
- Two independent chats cannot read each other's conversation context.
- Saved conversations survive an application restart.
- A fresh evaluator can follow documented setup steps and complete all three
  product flows using local Ollama. Model download time is recorded separately.
- Record model latency and hardware for the demo; set a realistic latency target
  after measuring this laptop rather than claiming an untested speed.

## Assumptions

- A single-user local evaluation is sufficient; authentication is outside the
  first version. A local user identity still supplies user metadata to PostgreSQL.
- Gemini is acceptable as the cloud provider because the brief names cloud
  providers as examples rather than an exclusive list.
- The initial local-model candidate is Qwen3 4B, subject to testing on the
  laptop's 16 GB RAM and NVIDIA RTX 3050 with 4 GB VRAM.
- A browser application served locally satisfies the deployment requirement.
- The deadline notation and timezone need confirmation with the evaluator.
- Development remains local on the user's current network. Publishing is deferred.

## Scope

Include FastAPI, PostgreSQL, Pi integration, transcript ingestion/retrieval,
independent persistent chats, visible provider selection, grounded generation,
an essay skill, a safe artifact viewer, meaningful tests, and handoff documents.

Exclude billing, team administration, autonomous external actions, arbitrary
code execution, public hosting, and production multi-tenant authentication.
These do not serve the immediate local evaluation flows.

## Key flows and acceptance criteria

- New chat: creates a session; selecting another chat loads only its messages.
- Answer: retrieves transcript passages, cites actual source identifiers, and
  displays an insufficient-evidence state when retrieval cannot support an answer.
- Essay: follows a checked-in writing skill, uses evidence from the knowledge base,
  tracks approximate word count, and produces skimmable Markdown.
- Artifact: renders Markdown or complete HTML/CSS in an adjacent panel. Generated
  HTML is treated as untrusted; scripts, parent-page access, and external network
  requests are blocked by the chosen sandbox and content security policy.
- Provider change: changes configuration without code edits and is visible to the
  user. A local-model failure must never silently send data to a cloud provider.
- Failure: missing key, unavailable model, timeout, empty retrieval, and database
  outage each produce clear user messages and structured diagnostic logs.
- Persistence: records sessions, messages, timestamps, and user metadata in
  PostgreSQL; the agent framework's own history cannot replace this requirement.

## Risks and trade-offs

- Small-model quality: evaluate retrieval, tool routing, essay coherence, and
  citation support before fixing the model choice.
- Limited GPU memory: limit simultaneous generations and benchmark context size;
  use staged essay generation if one large prompt performs poorly.
- Hallucinations: supply bounded evidence, validate citation identifiers, test
  unsupported questions, and distinguish synthesis from verbatim source material.
- Cloud cost and privacy: local by default; cloud use requires explicit provider
  selection and an API key. Free-tier availability and limits are account-dependent.
- Unsafe artifacts: enforce rendering restrictions, not just instructions to the model.
- Network restrictions: record download prerequisites and failures honestly;
  do not claim reproducible setup until tested from a fresh environment.
- Public handoff: exclude keys, private account data, the confidential assignment
  PDF, and unsanitized coding-agent logs from any eventual public repository.

## Implementation order

1. Verify local Ollama inference and a minimal Pi/FastAPI integration.
2. Build transcript ingestion, source metadata, retrieval, and grounding checks.
3. Add PostgreSQL persistence and API/session isolation tests.
4. Build the chat UI, source inspection, and explicit provider selection.
5. Implement the writing skill and secure artifact viewer.
6. Test failure states and write architecture, design, and operational documentation.
7. Verify fresh setup and prepare the camera-on demo script and recording checklist.

## Handoff

Deliver source, README, this PRD, design.md, architecture.md, sanitized coding-agent
logs (including failures and corrections), automated tests, manual UI test plan,
and a 2-3 minute demo video recorded with the user's camera enabled.

GitHub publication, YouTube upload, and submission are later steps and have not
been performed. The user has explicitly deferred GitHub pushes.
