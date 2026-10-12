# Design

## User experience

A product/growth practitioner begins with a question or a starter prompt. The left
sidebar holds independent conversations. The center holds the chat and source chips.
The right panel opens Markdown or HTML artifacts with Preview, Source, Copy, and
Download controls. On small screens the artifact becomes an overlay and the sidebar
is collapsible. The research-studio palette uses a navy sidebar, cobalt actions,
lime highlights and a cool light canvas. Trebuchet MS with local fallbacks avoids
external font requests. Compact corners, clear focus outlines and dark-mode colours
carry through the composer, source chips, dialogs and artifact viewer.

The composer exposes output mode and provider. Local is the initial default, and the
browser remembers the user's selection. Settings explains data movement and setup.
A saved cloud key is labelled configured until an actual response succeeds.

## Grounded answer flow

New chat creates a PostgreSQL session. Sending persists the user message and returns
a job ID. The UI polls progress and can resume after refresh. Retrieval provides
bounded excerpts with episode metadata. The model receives only this evidence plus
short conversational context, and is instructed to abstain when unsupported.
Citation identifiers must match retrieved source IDs before a draft is accepted.
A second model pass checks factual support and rejects uncertain verdicts. Source chips open exact excerpts, timestamps when available, and original links.

## Essay and artifacts

The dedicated Ship30 skill chooses audience/promise, a strong hook, useful structure,
skimmable headings, and an actionable ending. Four bounded sections target about
1,250 words and receive one length refinement when necessary. Warnings expose a
missed word target rather than silently claiming compliance. Continuity uses earlier
section endings; this is a laptop-memory trade-off and can cause repetition.

Markdown renders with raw HTML disabled. HTML receives sanitization, restrictive CSP,
and an iframe with an empty sandbox permission list. External resources, scripts,
forms, and navigation are removed/blocked. Source view uses textContent.

## State and failure design

Empty library, unavailable database/agent/model, invalid credential, quota, and timeout
have distinct messages. No failure silently switches to cloud. A single generation
queue avoids exhausting 4 GB VRAM. Cancellation discards results at stage boundaries;
it does not promise immediate interruption of the model transport. Restarted jobs
become explicit errors. Conversation and artifact state survives normal restarts.

## Scope and limitations

This is single-user local UX, not authentication. Keyboard form submission and labelled
controls are provided; formal accessibility audit and cross-device acceptance remain
unperformed. Error and progress states are implemented, but the manual plan must be
executed before claiming submission acceptance.
