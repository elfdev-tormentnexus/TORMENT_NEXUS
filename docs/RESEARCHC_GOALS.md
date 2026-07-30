# Research C goals — measured uncertainty as a compute gate

Status: **future work after the Research B release boundary.** Nothing in this
document changes Research B behavior, its vector formats, or its release
artifacts.

## Origin

Sable was asked whether combining vectors with token log probabilities could
improve efficiency. The useful idea survives, but the representation needs a
clean boundary: semantic vectors describe meaning, while log probabilities
describe one model's uncertainty about one token under one prompt and sampler.
They should meet at decision gates, not be concatenated into one geometry.

## Governing hypothesis

Logprob-derived measurements can reduce average compute when they are taken
from a model call that already had to happen and are allowed only to cancel a
later expensive step.

They are not truth scores. They are model-, quantization-, prompt-, context-,
and sampler-specific observations. High confidence must never authorize an
edit, bypass a guard, skip verification, or certify a factual claim.

## Goal 1 — early refusal in the two-model repair loop

Research B's Super Dev flow spends three large units per candidate:

1. the 14B plans and reviews;
2. the 7B drafts one bounded patch; and
3. trusted code applies it and runs the fixed regression gate.

Request logprobs from the 14B call and calculate length-normalized surprisal
over the selected target and proposed change. An unusually uncertain plan may
stop before the 7B is called. Do the same over the 7B's exact `find` and
`replace` payload; an unusually uncertain patch may stop before any write or
regression run.

Current expected cost per candidate is:

```text
C14B + C7B + Ctests
```

With a refusal-only gate it becomes:

```text
C14B + q(C7B + Ctests)
```

where `q` is the measured fraction of plans that clear the gate. The gate is
valuable only if it rejects bad candidates often enough without discarding a
large share of candidates that would have passed every existing guard.

### Deliverable

A held-out comparison table over accepted and rejected historical candidates:

- mean chosen-token surprisal;
- worst-decile surprisal;
- top-one/top-two margin when available;
- whether the 7B produced a parseable, unique patch;
- whether the capability guard accepted it;
- whether the regression gate passed; and
- wall time and model time avoided by each simulated threshold.

Choose no threshold until the table exists. A null result is a valid result.

## Goal 2 — measured memory confidence

The durable-memory extractor currently asks the 4B to emit a confidence number
about its own JSON. Automatic lexical memory injection later uses that number
as a tie-breaker. Explicit semantic search remains cosine-ranked and must stay
separate.

For a labelled set of durable and non-durable utterances, record logprobs from
the extraction call and score only the generated memory/category span. Compare:

- the model's self-reported confidence;
- mean chosen-token surprisal;
- worst-decile surprisal;
- top-one/top-two margin;
- exact factual entailment by the operator's message;
- correct category; and
- whether the memory passed the existing deterministic rejection rules.

This experiment primarily improves evidence quality. It does not eliminate the
extraction inference that produced the logprobs. Any compute saving would be
downstream: fewer low-quality memories entering later prompts and fewer bad
candidates competing in automatic recall.

## Goal 3 — cheapest-first model routing

For a task that would otherwise always use an expensive model, a smaller model
may run first and escalate only when its calibrated uncertainty gate fires:

```text
Cexpected = Csmall + p(escalate) * Clarge
```

This saves compute only when:

```text
p(escalate) < 1 - Csmall / Clarge
```

Research B ordinary conversation already starts with its 4B director, while
the 7B and 14B are explicitly requested editing roles. Adding automatic
escalation to ordinary chat would increase, not reduce, its present compute.
Test this routing only on workflows that already budget the larger model.

## Representation boundary

Keep uncertainty beside an artifact rather than inside its semantic vector:

```text
semantic_vector
mean_surprisal
peak_surprisal
top1_top2_margin
model_digest
prompt_digest
sampler_record
```

Concatenating these values onto embeddings would change cosine geometry,
invalidate existing caches and thresholds, and mix semantic location with
serving telemetry. Machinespirit may visualize the sidecar, but must not
pretend it is another semantic dimension.

## Experimental controls

- Benchmark logprobs off, chosen-token logprobs, top two, and top ten. The
  model already computes logits for sampling, but candidate selection,
  serialization, transfer, and storage are not free.
- Fit thresholds on one set and report them on a separate held-out set.
- Bind every result to model file digest, quantization, prompt digest,
  temperature, top-p, and relevant llama-server revision.
- Report false refusals alongside compute saved. Saving compute by silently
  throwing away good work is not an efficiency result.
- Log measurements and decisions, never private prompt or memory text.
- Preserve every existing deterministic guard and regression gate.

## Release boundary

Research B already exposes per-token entropy when its vector panel is active.
Research C should reuse that plumbing where appropriate, but no Research C
threshold or routing behavior belongs in a Research B patch. The comparison
tables come first; implementation follows only if the measurements justify it.
