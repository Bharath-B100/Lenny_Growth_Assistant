# Saved development examples

The project database includes a real Gemini QA and a 1,190-word Ship30 essay on
Sean Ellis's user-disappointment survey. The essay was generated through Pi,
passed the model evidence review, and is exported as `deliverables/cloud-essay.md`.
The review pass is fallible; some introductory and causal claims are interpretations
that should be checked before reuse. The PDF's accuracy target is not yet measured.

The earlier local Markdown sample was manually corrected after its draft repeated
ambiguous transcript wording. It is exported as `deliverables/local-example.md` and
marked as manually reviewed in stored metadata. Do not describe it as an untouched
model success. Source cards remain available in the app.

Cloud authentication is fixed. Subsequent requests can hit Google's free-tier quota;
manual selection of Local Ollama continues without enabling paid billing. Local
HTML generation is slower because the laptop GPU holds only part of the model.

Use real saved conversations for the demo and identify pre-generated examples clearly.

`deliverables/essay-brief.html` is the saved essay converted to styled HTML without
new model claims. Direct HTML generation failed under cloud quota; local inference
returned empty output. The deterministic conversion is explicitly identified.
