# Verification — 12 October 2026

This report separates completed jobs from answers that passed evidence review. Task.pdf
defines the requested project and final submission, but does not authorize publishing it.

## Live model results

The local provider was Qwen3 4B Instruct through Docker Ollama, with PostgreSQL and the
Pi agent running. The transcript index contains 303 episodes and 34,265 passages.

| Check | Result |
|---|---|
| Broad baseline, 20 supported prompts | 6 marked cited, 6 insufficient, 8 rejected. This run preceded the latest reliability fixes; its cited answers still included factual overreach. |
| Broad baseline, 5 unsupported prompts | All 5 abstained as insufficient evidence. |
| Targeted answer and follow-up after fixes | Both completed and passed the app's citation/evidence gate (130 and 139 words). They state that the survey asks about the whole product, not an individual feature. |
| Markdown artifact | Saved as `deliverables/verified-ollama-markdown.md`; completed the citation/evidence gate after the group-ignore correction. It is about 350 words, so treat it as a concise checklist rather than a long-form brief. |
| HTML artifact | Saved as `deliverables/verified-ollama-html.html`; completed the citation/evidence gate and the saved output was checked for safe rendering. |
| Essay | Rejected after 701.6 seconds. The evidence gate tried two targeted corrections; no essay artifact was saved. The final user-facing message recommends narrowing the topic or inspecting the sources. |
| Unsupported evaluator-password request | Abstained as insufficient evidence. |

The 20/5 run is a completed baseline, not a passing quality score. The targeted fixes
addressed the observed product-versus-feature inference, citation handling, overlong
answers and advice to ignore somewhat-disappointed users. The targeted answer and saved
artifacts passed their app gates, but neither citations nor a separate small-model
reviewer prove every claim. No full 20/5 rerun was made after the fixes. The essay is
still a demonstrated failure, not a remaining transport problem.

## Gemini

Gemini returned a cited answer and abstained on the unsupported request in an earlier
check. Google then returned `PROVIDER_QUOTA` on later generation requests. The key is
configured but further Gemini output is unverified; no billing, key or account changes
were made. The local essay result is the latest essay acceptance result.

## Application and data checks

- API, Pi agent, Docker PostgreSQL and local Ollama responded in the live setup.
- Corrected the ingested `Alex Hardiman` guest-name typo. Reingestion preserved 303
  episodes and 34,265 passages; the repeat pass reported zero changed files.
- Saved insights persisted across browser reload and reopened in their chat. Dark mode
  persisted; Discover showed six question starters; essay audience reached the API.
- Script-free API reference displayed its endpoint table and OpenAPI link. Markdown
  download saved in the browser. The updated app screenshot is
  `deliverables/updated-app.png`.
- Earlier operational checks covered Docker restart persistence, UUID ownership
  isolation, mobile layout, sandboxed HTML rendering and clipboard copy.

## Automated checks

- **51 Python tests passed** with `LENNY_INTEGRATION=1`, including PostgreSQL checks in
  isolated temporary schemas. One third-party AnyIO deprecation warning remains.
- **10 Node transport tests passed**, including split-UTF-8 NDJSON and interrupted
  stream handling.
- `compileall` passed for `backend`, `scripts` and `tests`.
- Both Docker builds and isolated app/bridge container checks passed earlier.

## Still required for full handoff

1. Improve and re-run essay generation until an approximately 1,250-word essay passes
   evidence review. No verified local essay artifact currently exists.
2. Run the 20 supported and 5 unsupported semantic checks again after the final fixes;
   the baseline was completed before those fixes and had many supported-answer failures.
3. Demonstrate a fresh-machine installation including dependency and model downloads.
   Browser UUID ownership is suitable for a local demo, not production authentication.
4. Record and upload the camera-on 2–3 minute demo, publish the repository when the
   network restriction permits, and submit the requested links. Those actions require
   the user's camera/account and remain undone.

The local app remains available at `http://127.0.0.1:8000/`. It is useful for review and
continued work, but the project is not yet ready to claim full Task.pdf acceptance.

## Research studio UI verification — 12 October 2026

- Redesigned colours, typography, buttons, navigation, composer and dialogs in
  `frontend/studio.css`; all existing integration IDs remain intact.
- Fixed new-chat scroll reset and dark-mode user-message contrast.
- Checked desktop (1366px) and narrow mobile (390px) layouts: no horizontal overflow.
  Toggled dark mode and confirmed live library search returned the Sean Ellis episode.
- Live GET checks returned HTTP 200 for root, CSS, JavaScript, liveness, readiness,
  status, library search, API documentation and OpenAPI schema. No browser console
  errors were observed. These checks do not constitute all-route live generation testing.
- Re-ran 51 Python tests with database integration enabled and 10 Node transport
  tests; all passed. JavaScript syntax check passed. Model responses in automated
  API tests are controlled test responses, not proof of cloud/model quality.
- Automatic approval review rejected the FastAPI restart with “blocked by policy”.
  The latest backend grounding change is therefore not confirmed loaded in the
  running process; static frontend changes are visible.
- Gemini quota and unaccepted long-form essay remain the limitations described above.
