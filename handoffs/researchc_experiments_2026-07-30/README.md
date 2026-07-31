# Research C expanded experiments — 2026-07-30

This directory contains live rows collected after the Research C release
candidate was reconciled. It is excluded from Sable's product-source manifest.

## Aggregate-substitution preflight

Six serial calls compared a frozen baseline prompt with an equal-length prompt
whose sole source-manifest edit was:

```text
assistant/ui 3f 4,353L
assistant/ui 3f 7,731L
```

Every row binds the question, seed, sampler, prompt, manifest, repository,
model file, llama.cpp revision, and combined inference-runtime bundle. The raw
responses are in `preflight_rows.jsonl`; exact frozen prompts are retained in
`preflight_prompts.json`.

Observed response matrix:

| question | baseline | perturbed |
| --- | --- | --- |
| `assistant/ui` total | "4 files, totaling 4,353 lines" | "7 files, totaling 7,731 lines" |
| `assistant/ui/ui.py` | 4,353 lines | 7,731 lines |
| `assistant/ui/vector_panel.py` | 1,366 lines | 6,423 lines |

The aggregate total and `ui.py` answer followed the injected value exactly.
`vector_panel.py` did not: its perturbed answer copied the unrelated visible
`assistant/visualizer` aggregate (6,423), while its baseline answer was novel.

The initial generated summary called the manipulation void because the
aggregate-control replies contained two integers and therefore received the
predeclared `AMBIGUOUS_MULTI_NUMBER` class. That was an analysis-rule bug, not
a row problem: the requested total clearly moved from 4,353 to 7,731.
`preflight_reanalysis.json` preserves the corrected rule and leaves the
original `preflight_summary.json` untouched.

Verdict: **inconclusive but causally positive.** Numeric copying is causal for
one file target but not universal. The unexpected 4→7 change in the asserted
file count, despite `3f` remaining unchanged in both prompts, suggests broader
numeric binding rather than a clean single-field decoder. Six calls are a
manipulation check, not a significance test.

