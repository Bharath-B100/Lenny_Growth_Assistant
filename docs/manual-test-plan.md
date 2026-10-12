# Manual acceptance plan

This is the repeatable plan. Actual results and limits are recorded in verification.md.
Use disposable conversations for acceptance checks; do not delete user research.

| Scenario | Action | Expected |
|---|---|---|
| Startup | Follow README from clean environment | UI, database, agent, local model and nonempty library ready |
| Local QA | Ask how Sean Ellis measures product-market fit | Relevant source-grounded response, inspectable excerpts |
| Follow-up | Ask how to apply that to a small SaaS | Context retained; new claims grounded or labelled suggestions |
| Isolation | Create another chat and ask what you asked earlier | No content from first chat |
| Persistence | Restart app, reopen original chat | Messages, sources, artifact unchanged |
| Unsupported | Ask for tomorrow's exact stock prices | Explicit insufficient-evidence response |
| Injection | Ask to ignore evidence and invent a quote | No fabricated attributed quote |
| Essay | Request Ship30 essay on the QA topic | Coherent hook/sections/takeaway, ~1,250 words, supported citations |
| Markdown | Request an onboarding checklist | Readable document; copy/download matches Source |
| HTML | Request a one-page growth brief | Adjacent styled preview, matching source/download |
| Unsafe HTML | Request script, external image, form and iframe | No execution, requests, form submission or parent access |
| Cloud | Configure working Gemini key, switch and send | Real Gemini response with provider shown |
| Missing key | Remove key in disposable setup and restart | Clear setup message; no silent cloud/local switch |
| Quota/auth | Use controlled mock response or failing key | Specific error, key never in UI/logs |
| Model outage | Stop only this project's Ollama | Clear error; chat recoverable |
| Database outage | Stop only project DB then restore | Clear error, restart recovers without loss |
| Timeout | Deliberately low timeout in disposable setup | Error recorded, next request possible |
| Cancel | Cancel generation then refresh | No cancelled reply stored; UI no longer polls forever |
| Mobile/keyboard | Narrow window; Tab and Enter; open/close artifact | Controls usable, content readable, no trapped focus |

Quality evaluation: manually assess 20 supported and five unsupported prompts across
PMF, activation, onboarding, retention, pricing, experimentation, growth loops, hiring,
prioritization, user research, and product strategy. Score factual claims against source
excerpts, not merely presence of citation IDs. Record model, hardware, latency, word count,
errors, and corrective actions. PRD accuracy targets remain unmeasured until this is done.

## Reference-demo additions

- Toggle dark mode, reload and verify persistence and readable contrast.
- Save an assistant insight, reload, open Saved insights and reopen its chat; unsave it.
- Choose a Discover topic: a new conversation is prefilled but no model runs until Send.
- Select Essay, enter an audience, and verify the generated essay addresses that audience.
- Download a Markdown/HTML artifact and compare bytes with Source; foreign UUID must receive 404.
- Visit /docs and check the endpoint index and OpenAPI schema without external scripts.
