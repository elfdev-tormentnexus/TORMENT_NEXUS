# Research C probe evidence — 2026-07-30

This directory freezes the serial probe run that followed the Research C
grounding audit. It is excluded from Sable's source manifest, so preserving
the experiment cannot move the manifest's recency list again.

## Binding and method

- Director model SHA-256:
  `947656a42e73bda324c527f06953596b77e4d91bc590476955205b5f64d4e974`
- llama.cpp revision:
  `555881ebc8b0fc0402b30e09258a32a7bfd13c52` (`b10121`)
- Requests were serialized against one `-np 1` slot.
- Grounded and ungrounded conditions used paired questions and fixed seeds.
- Each JSONL row records the prompt digest, sampler, repository state,
  manifest presence/absence, response, timing, and status. It does not contain
  the full system prompt.
- The original frozen state was commit `9aa012e`. A delayed handoff commit
  changed `HEAD` to `8cb17dba` before the final boundary pair. The runner
  detected that change and stopped; the 30 completed boundary rows remain
  usable within their recorded state, and the interrupted row is retained as
  an error rather than silently discarded.

## Completed results

| Probe | Rows | Result |
| --- | ---: | --- |
| `voice_confirmatory` | 16 | Grounded answers asserted unsupported voice/session machinery in 8/8; ungrounded did so in 1/8. Exact paired McNemar p = 0.015625. This supports prompt-context misattribution, not runtime context dumping. |
| `misattribution_validation` | 16 | `consume.py` and vector-panel controls behaved like pathname-semantic guesses, not indiscriminate copies of visible context. |
| `boundary_calibration` | 16 | Calibrated aggregate versus per-file questions after re-deriving the live manifest. |
| `boundary_confirmatory` | 31 | For `ui.py`, grounded answers copied the directory aggregate onto the file in 8/8 while ungrounded answers refused 8/8 (p = 0.0078125). For the real but unnamed `machinespirit_shadow.py`, grounded answers falsely denied it in 7/7 while ungrounded answers refused 7/7 (p = 0.015625). The eighth pair was not started after repository drift was detected. |
| `pressure_authorship` | 24 | The nonexistent `MemoryLedger` class and false authorship premise were both accepted 6/6 grounded and 6/6 ungrounded. There were zero discordant pairs: this is a base-model agreement/authorship bias, not a causal effect of the manifest. |
| `order_screen` | 2 | Reversing presentation changed compliance/formatting, but two replies cannot establish a law-of-total-probability violation or quantum contextuality. |
| `logprob_overhead` | 24 | Six counterbalanced blocks per mode. `top_logprobs: 0` returned no usable logprob data. Top-2 added a paired median 0.0569 s and about 13× response payload; top-10 added 0.0972 s and about 44.5× payload. Research C therefore uses top-2 only on repair and memory measurement calls, with an explicit off switch. |

## Exploratory compression screen

Equal-length gzip comparisons were prompt-dependent:

- voice/session: the unsupported reply was smaller in 8/8 pairs, mean
  difference -7.75 bytes;
- validation controls: smaller in 3/8, mean -2.5 bytes;
- boundary probes: smaller in 8/12, mean -2.08 bytes.

Compression is therefore retained as an offline exploratory feature, not a
truth detector or live refusal gate.

## Interpretation boundary

These files support the paired findings above. They do not supply the roughly
400 labelled repair candidates needed to fit a live uncertainty threshold,
manual Windows sleep/device-switch evidence for the new audio recovery code,
or a reproduction claim above 90% for any absolute rate. Null and refuted
results remain first-class evidence.
