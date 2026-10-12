# Reference demo comparison — 12 October 2026

The supplied transcript is a reference demonstration, not permission to publish or
change credentials. Task.pdf remains the requirement checklist.

| Reference feature | This project's implementation |
|---|---|
| Light/dark appearance | Added persistent theme toggle |
| New inquiry and saved chats | Existing PostgreSQL conversations and history |
| Source cards and episode playback | Existing excerpts, source links and timestamp links; conflicting upstream metadata now hides unverified video links |
| Saved insights | Added per-message bookmarks, ownership checks and a saved-insights list |
| Discover topics | Added six starter topics that prefill a new conversation |
| Essay audience | Added an audience field passed to the essay generation request |
| Essay and HTML/Markdown viewer | Existing dedicated Ship30 skill, source/preview/copy and server download |
| Local/cloud model selection | Qwen3 4B Instruct in Ollama and Gemini, visibly selected; no silent fallback |
| Docker and persistence | Docker Ollama/PostgreSQL; container definitions for backend and Pi bridge |

## Do not copy inaccurate demo claims

- Do not show an invented match percentage. Lexical retrieval rank is not a calibrated probability or factual confidence score.
- This implementation uses vanilla JavaScript, FastAPI, Pi and PostgreSQL full-text retrieval. It does not use React, Chroma or Llama 3.2; those are details of the reference demo.
- The reference's 741-word essay is shorter than the assignment's approximately 1,250-word target. The app targets 1,125–1,375 words and reports the actual count.
- Keep the final camera-on demonstration within 2–3 minutes. Use genuine prepared results and disclose skipped generation waits.
- A citation or model-review approval does not prove accuracy. Check the actual excerpt, especially survey conditions and numerical claims.

## Remaining handoff

See verification.md for the latest live checks and limits. GitHub publication is
deferred under the user's restriction. The user still needs to record/upload the
camera-on video and submit the required links. A source ZIP is not a replacement
for the evaluator's public repository requirement.

## Research ideas used

The Ship30 guide recommends a clear headline that tells readers the topic, audience, and payoff; an introduction that matches that promise; scannable headings and bullets; varied sentence rhythm; and removing repeated material. The sourced skill translates those ideas into the essay flow while keeping factual transcript claims cited and not inventing personal stories. Source: https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide (checked 12 October 2026).

OpenAI’s API guidance points out that model behavior can vary between versions and recommends repeatable evaluations. The local `scripts/quality_benchmark.py` now prepares 20 representative supported prompts and five unsupported prompts; it records sources for human claim scoring instead of treating a citation or model-review pass as proof. Source: https://developers.openai.com/api/reference/overview (checked 12 October 2026).
