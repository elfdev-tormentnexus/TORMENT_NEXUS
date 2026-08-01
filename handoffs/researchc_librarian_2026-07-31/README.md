# Research C shadow-librarian probe

This handoff preserves the first corrected, identity-bound model result for the
Research C librarian experiment. The librarian remained an observer throughout:
its return value could not change retrieval, Sable's prompt, or Sable's answer.

## Result

The fixed eight-case boundary set was presented twice, once in baseline order
and once with the same candidate pool reversed:

| Measure | Result |
| --- | ---: |
| Strictly valid decisions | 11/16 (68.75%) |
| Correct valid decisions | 9/16 (56.25%) |
| Forward/reverse agreement | 1/8 (12.5%) |
| Mean model-call wall time | 2.146 seconds |
| Mean prompt size | 4,568 bytes |

The model was `Qwen3-4B-Instruct-2507-Q5_K_M.gguf`, bound by SHA-256 in
`result.json`. It ran through a dedicated authenticated loopback llama.cpp
service that was started for the probe and stopped afterward. The existing
Sable services were not reused or restarted.

The decision contract used a strict JSON object containing a complete
candidate-ID permutation plus a trusted prefix count, rather than a second
free-form selected-ID list. That reduced one failure class but did not make the
result promotion-worthy. Five of sixteen outputs were still structurally
invalid. Reversing candidate presentation changed seven of eight case outcomes
or rankings. The model therefore remains shadow-only.

## Deterministic boundary

The same run reproduced the non-model baselines:

- Built-ins only: 18/18 candidate, top-1, and top-3 recall; 10/10
  known-unknown abstention; no specialist intrusion.
- Synthetic specialist bait: 18/18 candidate, top-1, and top-3 recall remained,
  but known-unknown abstention fell to 5/10 and specialist passages entered
  2/18 positive selections.

These failures were declared before the model run. The librarian did not beat
them reliably.

## Measurement correction

An earlier draft metric credited a malformed abstention as correct whenever
abstention was the expected behavior, and counted two malformed outputs with
empty selections as order agreement. The stored result fixes both errors:

- a decision must parse and validate before it can count as correct;
- both decisions must be valid before they can count as order agreement.

This correction changed the apparent scores from 87.5% task accuracy and 62.5%
order agreement to the reported 56.25% and 12.5%. The corrected definitions
are regression-tested.

## Interpretation limits

This is a finite engineering gate, not a population estimate. It is one run of
one model, quantization, prompt contract, server closure, sampler, and host.
The result does not show that every 4B model, every Qwen model, or every LLM
librarian would fail. It does show that this exact candidate is not safe to
promote. The file hashes in `result.json` bind the probe-time uncommitted
working-tree snapshots; the base Git commit identifies their parent, not the
implementation by itself.

No raw query, reference excerpt, path, URL, model output, or bearer key is
stored here. `result.json` contains closed outcomes and reproducibility
digests only.

## Preregistered shipped-model follow-up

The unchanged follow-up in `shipped_director_followup_spec.json` was completed
after the first result. The already shipped Qwen3 4B abliterated Q8 weights,
running in a separate GPU service with thinking disabled, improved strict
format validity to 15/16 and forward/reverse agreement to 5/8. Task accuracy
remained 9/16. It therefore also failed the preregistered all-perfect
engineering gate and remains shadow-only. Closed results are in
`shipped_director_followup_result.json`.
