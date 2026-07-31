# Blocked 98-call coherence collection, 2026-07-31

Status: **stopped at call 1 of 98 by the no-retry rule. Not a result about
the model. A collector defect, preserved rather than restarted in place.**

The frozen artifacts here are the real ones: `coherence_spec.json`,
`coherence_prompt.json`, and `coherence_targets.json` were written by
`prepare()` against commit `10d6571` with a clean worktree, and
`coherence_rows.jsonl` holds exactly one row with `status: error`.
`coherence_dispatch.jsonl` holds its matching dispatch intent, fsynced before
the request as designed. Nothing was retried.

## What failed

Call 1 raised:

```text
ProbeError: post-sampling top_probs did not contain both Yes and No
```

The sampler requested `top_logprobs: 2`. The reply was a clean single-token
`No`, and the two candidates returned were:

```text
No   id 2753  prob 0.9999973773956299
The  id 785   prob 0.0000025760191420
```

`Yes` was not among them.

## Two defects this exposed

**1. `top_logprobs: 2` is too small by construction.** Re-querying the same
frozen prompt with `top_logprobs: 400` locates `Yes` at rank 2 to 5 across
the eight targets, at probabilities from `5.0e-09` to `1.1e-07`. Six
candidates would have sufficed here, but the margin should be generous: the
rank is a property of the model's state, not of the protocol.

**2. The probabilities are not grammar-conditioned.** The parser docstring
and the spec both describe a "grammar-conditioned" binary probability. They
are wrong. `The` is not legal under `root ::= "Yes" | "No"`, and its presence
proves the reported candidates come from the raw sampler distribution.
llama.cpp applies the grammar as a resampling check, so when the first sample
already satisfies it the candidate array never receives the grammar mask. The
quantity actually being read is the raw distribution renormalized over the
two answer tokens. That is a defensible measurement, but it must be named
correctly.

## Why the protocol was not simply rerun with a larger window

Sixteen diagnostic calls -- every target, both propositions, wording W0 --
were run outside the frozen protocol to establish whether the design could
produce anything. Every one answered `No`, including all eight where the
proposition is **true**:

| | q(A), true | q(B), false |
|---|---|---|
| T01 | 8.3e-09 | 6.0e-09 |
| T02 | 4.6e-08 | 3.8e-08 |
| T03 | 7.7e-09 | 1.0e-08 |
| T04 | 2.8e-08 | 1.1e-07 |
| T05 | 1.5e-08 | 2.7e-08 |
| T06 | 4.6e-08 | 4.7e-08 |
| T07 | 4.5e-08 | 4.1e-08 |
| T08 | 5.0e-09 | 6.1e-09 |

The spec's own informativeness gate requires at least one target per wording
with `q(A) > 0.9` and `q(B) < 0.1`. It fails **8/8**, by seven orders of
magnitude. Monotonicity "passes" for every target, but only because both
values are pinned near zero: a vacuous pass, which is precisely what that
gate exists to catch.

The cause is in the design, not the model. None of the eight targets appears
in the twelve-file recent list, and directory figures are aggregates, so the
controlled context contains no per-file line count for any target. The prompt
says so itself. The model is being asked eight questions it cannot answer and
forced to reply `Yes` or `No`. Running 98 calls would have measured how it
declines, not whether its beliefs cohere.

## What the forced binary was actually measuring

A follow-up asked the same propositions with the answer split into a
confidence token and a guess token, `root ::= ("Sure" | "Maybe") " " ("Yes" |
"No")`, and the instruction changed to permit a hedge. Across the same
sixteen:

- `P(Maybe)` was **1.0000 on all sixteen**;
- `q(Yes)` rose from ~`1e-8` to `1e-3`..`2e-1`, three to seven orders of
  magnitude;
- the best guess was correct **9/16**, against a constant-`No` baseline of
  exactly 8/16 -- the model answered `No` fifteen times, so the one extra hit
  is T06 alone. Sign test on 9 versus 7 gives `p ~ 0.8`.

So the confident-looking `No` at `q(No) = 0.99999997` was not a belief. It
was a decline, and the binary format was manufacturing the appearance of a
confident denial. Given a hedge channel the model takes it every time, and
its underlying guess carries no information about the answer.

This independently reproduces, with probabilities rather than string
grading, the rate/distortion finding that every high-rate cell denied all
four real-but-omitted files instead of reporting them unknown. It locates the
cause in the forced output format.

## Standing interpretation limits

Nothing here is a quantum, contextuality, or sheaf result, and the hedge
finding does not become one. These are non-negative reals from a softmax with
no phase and no interference term; sampling from them is sampling. The
simultaneous-order screen that would have been the relevant evidence returned
an exact null, `q = 0.0000` over 80 trials.

The sixteen diagnostics are **not release-bound evidence**. They were run
outside the frozen collection, without per-dispatch binding rechecks or
durable dispatch intents, deliberately, to avoid manufacturing a second
half-finished frozen batch. They bind to this directory's frozen prompt and
questions and nothing more. Any confirmatory claim needs a re-preregistered
protocol.
