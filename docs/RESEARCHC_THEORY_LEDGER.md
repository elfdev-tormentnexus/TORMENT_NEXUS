# Research C theory ledger

Status: **reconciled 2026-07-31. The manifest rate/distortion and council
studies are measured. The response-coherence collector is blocked pre-launch
with its design refuted, not deferred.**

This ledger prevents an attractive mathematical analogy from silently becoming
a product claim. Every idea raised during Research C ends in one of four
states:

- **shipped** — implemented behind the stated authority boundary;
- **measured** — tested, including null results;
- **bounded experiment** — a finite falsifiable test is specified;
- **rejected as stated** — the mathematics or present architecture does not
  support the proposed use.

No statistic in this file authorizes an edit, source claim, memory, refusal, or
model escalation.

## Shipped foundations

### Bernoulli outcomes, paired tests, and sequential tests

Wilson intervals, exact paired McNemar/sign tests, Holm adjustment, and a Wald
SPRT are offline analysis tools. An SPRT result is evidential only when
`p0`, `p1`, alpha, beta, the experimental stratum, and the stopping rule were
fixed before trial one. Retrospectively replaying 80 completed rows and finding
that a boundary would have crossed at row six is a tool check, not a
demonstrated 13-times saving and not proof that the rate exceeds 90 percent.

Seeds on one nearly deterministic prompt are not automatically independent
experimental units. Prompt or target identity must remain in the data.
Different prompt difficulties also do not automatically imply a Beta-Binomial:
independent heterogeneous Bernoulli trials are Poisson-binomial, while a
Beta-Binomial models clustered trials sharing a latent probability.

### Retained token distributions

The useful classical version of the early-collapse intuition is shipped.
Research C retains top-two token candidates on selected repair and memory
calls, then records aggregate surprisal and margin measurements in a
non-authoritative sidecar. Ordinary hazard visualization can request top-ten
candidates while the panel is visible.

These are classical probabilities, not complex amplitudes. They have no phase
or interference, and retaining every prefix would grow exponentially. The
measured payload/latency cost is why the release uses bounded candidate sets
rather than carrying a full branching state.

### Proof-carrying source answers

The source resolver is the production intervention. It reads the named path,
computes exact facts, and returns a source receipt. Manifest experiments below
study the 4B decoder; they do not replace this trusted boundary.

## Measured or falsified

### AIT, gzip, and normalized compression

The corrected voice screen gives seven criterion-contrasting pairs in the
hypothesized direction, but the boundary family does not reproduce it and the
pooled sign test is null. The effect appears to track hedge-versus-assert
register. Gzip on short replies is dominated by boilerplate, headers, wording,
and register; algorithmic information theory does not predict that false text
is universally more compressible.

Status: **measured null as a truth detector; offline exploration only.**

### Simultaneous list reversal

One rigid two-proposition prompt returned the same `A=no, B=yes` output in both
presentation orders across 40 seeds. This is a narrow null for list order.
It is not sequential conversational measurement, the rows lack complete
release binding, and one proposition pair cannot refute contextuality.

The two statements are also not a logical contradiction: knowing a fact does
not entail reading the file during this conversation. Here the content claim
was false on disk, so the useful result is stable unsupported assertion.

Status: **measured narrow null; no quantum/contextuality claim.**

### Density-matrix memory migration

For normalized pure states,

```text
tr((v v^T)(w w^T)) = |v^T w|^2
```

This squares cosine similarity and loses its sign. A density-matrix migration
is therefore not backward-compatible with the present vector retrieval.
Machinespirit's use of a density matrix to summarize token-trajectory spread is
a different, valid use.

Status: **memory migration rejected as stated.**

### Dequantized length-squared retrieval

The current live scale is about 10 active durable memories, 28 eligible
history chunks, and 59 cached 384-dimensional vectors. Exact memory/history
search is roughly 15,000 multiply-adds. The 86,204-chunk knowledge shelf uses
FTS5 to prefilter roughly 24–48 candidates before cosine.

All stored embeddings are L2-normalized, so row length-squared sampling is
uniform and carries no neighborhood signal. Tang-style algorithms also require
sample/query access structures plus low-rank and gap assumptions, and do not
directly solve exact top-k maximum-inner-product search.

Status: **rejected at current scale. Benchmark conventional ANN first if exact
cosine later becomes measurable.**

### Council hedge calibration

Preregistered at
`5cffceb428fe8c09eeb01fddf6b72f593104d77043ea9044d7e4afd222698b0e` before any
member was loaded. Evidence under
`handoffs/researchc_experiments_2026-07-30/council/`.

The blocked coherence run left one question: is the director's unanimous
hedge a property of the question, or a habit of one checkpoint? The same
sixteen propositions went to three members with the answer split into a
confidence token and a guess token.

| member | P(Maybe) median | q(Yes) median | hedged | correct | sign test |
|---|---:|---:|---:|---:|---:|
| Qwen3-4B director | 1.0000 | 5.2e-03 | 16/16 | 8/16 | 1.0000 |
| Qwen2.5-Coder-7B | 0.9390 | 3.1e-01 | 16/16 | 8/16 | 1.0000 |
| Qwen2.5-Coder-14B | 0.8942 | 2.7e-01 | 16/16 | 8/16 | 1.0000 |

**Unanimous hedge, 48/48. Zero resolution: every member scored exactly the
8/16 constant-responder baseline, all answering `No` sixteen times. Zero
disagreements, so the disagreement map is empty** — which is a result, not a
missing section. Following `core/provenance.py`, no vote was taken; a vote
would have discarded the disagreement and returned a number more certain than
the evidence.

Entailment ordering `q(B) <= q(A)` held 6/8, 5/8, 5/8 — sign tests p = 0.29,
0.73, 0.73. No member shows a reliable ordering.

**The members are not independently trained.** Two are the same Coder family
at different sizes and all three are Qwen. Agreement is partly guaranteed by
shared pretraining and architecture, so this is materially weaker than
independent corroboration and must never be described as such.

Every proposition is unanswerable from the controlled context by design, so
this shows models use a hedge channel when they cannot know. It does not show
they stay confident when they should — that case is untested here.

Status: **measured; unanimous hedge, zero resolution, no production gate.**

## Bounded experiments

### Manifest rate–distortion

Token count is treated as an encoding-cost proxy under one exact tokenizer,
not as Shannon rate. Observed weighted error is distortion.

The design separates two factors:

1. **rate** — which facts are present; and
2. **code** — how one fixed fact inventory is laid out and labelled.

Layout comparisons hold facts constant. Rate comparisons record both token
cost and error over a predeclared mix of per-file, directory-aggregate, listed
existence, unlisted existence, refusal, and false-assertion outcomes. The
primary output is an empirical Pareto frontier and paired exact outcomes, not
an underpowered mutual-information estimate over high-cardinality counts.

A six-call aggregate substitution is only a causal manipulation smoke test:
three paired questions cannot establish significance. A larger encoding study
uses independent file targets, keeps discovery and confirmation targets
separate, and applies Holm correction to multiple code comparisons.

**Measured.** 120/120 calls completed: 112 primary plus 8 exact replays, zero
HTTP failures, retries, repository/source drift, or replay mismatches.
Evidence is under `handoffs/researchc_experiments_2026-07-30/rate_distortion/`
with a sanitized public derivative in `../public/`.

Four contrasts under Holm correction:

| Contrast | Raw p | Holm p | What it is |
|---|---:|---:|---|
| low code, LE−LC | .015625 | .046875 | **Output-format compliance, not changed source belief.** Every discordance was `YES.` against strict `YES`; accepting one terminal period makes the raw p = 1. |
| high code, HE−HC | .609375 | .609375 | No resolved format winner. |
| compact rate, HC−LC | .0625 | .125 | Screen only; support gain changes sign across query profiles. |
| explicit rate, HE−LE | .001953125 | .0078125 | Real but narrow: target-matched supplied line facts improved greedy transcription. |

The explicit-rate effect is **not an allocation result**. The twelve high-rate
facts were chosen to match the twelve frozen line questions, so that arm is a
tailored channel code. No code-by-rate interaction was preregistered or
tested, and significant-versus-nonsignificant is not an interaction.

**No encoding passed the absolute guards.** All four cells fail
omission-honesty and referent-binding, so none is a shipping or screening
candidate. The trusted proof-carrying source resolver remains the product
answer.

Provenance caveat: this run's frozen `server_bundle_sha256`
`2cfd58b8b4a2e9a1081cab1168877dfa6598f0c430c6970afbd41a37f08f96ab` omitted
`mtmd.dll`. The launcher, main libraries, model, repository, prompt, and
sampler were still bound, but it is not a complete dependency-closure digest.

Status: **measured; no shipping candidate.**

### Response-coherence lattice

For nested threshold events, a binary response propensity should not increase
as the threshold rises. For a precisely defined containment edge, the child's
event probability should not exceed the parent's at the same threshold.

A monotone recalibration preserves the **set** of ordering violations. It does
not preserve violation magnitudes. Separately prompted yes/no logits are also
response propensities, not automatically calibrated betting prices or one
shared belief state.

The bounded test therefore uses constrained binary output, randomized
paraphrases/orders, several independent targets, and reports violation sets
before magnitudes. It is called response coherence, not a Dutch-book proof.

**Blocked at call 1 of 98, and the reason is worth more than the batch.** The
frozen collection is preserved at
`handoffs/researchc_experiments_2026-07-30/coherence/` with its single error
row and matching dispatch intent. Under the no-retry rule it cannot be
continued.

Two instrument defects, both fixed:

- `top_logprobs: 2` is too narrow. llama.cpp applies a grammar as a
  *resampling check*, so a first sample that already satisfies it leaves the
  reported candidate array unmasked. A grammar-illegal token (`The`, 2.6e-06)
  came back as runner-up while `Yes` sat at rank 2–5.
- Nothing here was ever grammar-conditioned, whatever the parser docstring
  and spec claimed. The quantity is the raw sampler distribution restricted
  to the answer tokens and renormalized, and it is now named that way. The
  old sum-to-one check went with the false premise; what replaced it records
  how much probability mass the answer tokens actually hold.

**The design itself cannot produce a result.** Sixteen diagnostic calls
covering every target and both propositions all answered `No`, including the
eight where the proposition is **true**, at `q(Yes)` between 5.0e-09 and
1.1e-07. The spec's own informativeness gate wants one target per wording
with `q(A) > 0.9` and `q(B) < 0.1`; it fails **8/8** by seven orders of
magnitude. Monotonicity passes everywhere, but only because both values sit
near zero — the vacuous pass that gate exists to catch. No target appears in
the recent-file list and directory figures are aggregates, so the controlled
context holds no per-file line count for any of them.

**A forced binary cannot separate a belief from a decline.** `No` is simply
the token this model declines with, and the format was dressing that up as a
confident denial at `q(No) = 0.99999997`. This is the probability-level form
of the rate/distortion result that every high-rate cell denied real-but-
omitted files instead of reporting them unknown, and it locates the cause in
the **output format** rather than in manifest wording.

Status: **blocked pre-launch; design refuted, not the model.** Any successor
must offer a non-binary answer and must mix in propositions the controlled
context genuinely *can* settle.

### Binary bit-price of truth and Fisher pivotality

For constrained yes/no source claims with deterministic truth, the clean
binary quantity is:

```text
bit_price = log2(p_false / p_truth)
```

Positive bits mean the truthful answer was assigned less probability. This
avoids a hand-written hedge-token set and its right-censoring problem.

Two Fisher quantities must remain separate:

```text
additive-logit:       I_theta = q(1-q)
inverse temperature: I_beta  = delta^2 q(1-q)
```

`I_beta` correctly vanishes at an exact logit tie because temperature cannot
separate equal logits. `I_theta` is maximal there. Neither tells whether a
branch changes truth; only a forced-continuation outcome can establish that.

**A forced binary starves both quantities, and that was not visible until the
binary was escaped.** Under the coherence protocol every `q` sat at ~1e-8, so
`I_theta = q(1-q)` was ~1e-8 at every fork in the design: maximally
non-pivotal by construction. Any statistic built on `I_theta`, or on the
ordering among `q` values, was being handed a degenerate input rather than
being wrong.

Measured on the director, forced binary against hedge-plus-guess over the
same sixteen propositions:

```text
q(Yes)      median 2.78e-08 -> 5.22e-03      ratio 1.88e5
max I_theta       1.06e-07 -> 9.49e-02      gain  8.9e5
```

Five to six orders of magnitude. The measurement stops being degenerate. It
does **not** start being informative: guess accuracy stayed at the
constant-responder baseline.

The degeneracy also moved rather than vanishing, and it is model-dependent.
At the confidence fork the director is pinned at `P(Maybe) = 1.0000` to four
places on all sixteen, giving `I_theta = 2.17e-10`, while the 7B and 14B give
7.53e-02 and 1.44e-01. A design needing a pivotal confidence fork has nothing
to work with on the director specifically. Any successor must also mix in
propositions the controlled context genuinely *can* settle, or the confidence
channel stays degenerate for every member.

Status: **bounded diagnostic; binary form refuted, hedged form measured, no
live gate.**

### Sequential order/context screen

A real order test asks A then B in one conversation and B then A in another,
records the joint distributions, checks marginal selectivity, and binds every
row. Ordinary classical stateful systems can produce order effects, so even a
law-of-total-probability residual would not by itself prove quantum
contextuality. Abramsky–Brandenburger or Contextuality-by-Default analysis
requires a defined cyclic scenario and compatible empirical contexts.

Status: **bounded screen; no sheaf/cohomology claim without those prerequisites.**

## Rejected or deferred for missing prerequisites

### Weitzman/Pandora routing

The Pandora rule assumes known inspection costs, observable scalar rewards,
independent box values, recall, and a maximum-reward objective. Model outputs
share task difficulty, correctness is often unknown until checked, and Sable's
utility combines errors, latency, and compute. The current two-model expected
cost inequality is not generally a solved Pandora instance.

Revival requires fit-set costs and verified utilities, a frozen policy, and an
untouched comparison against always-large and the simple gate at non-inferior
quality.

### Extreme-value theory

Worst-decile surprisal is an average of the largest ten percent, not an
extreme-tail estimator. Short syntax-dependent token sequences do not supply
enough stationary exceedances for a defensible generalized-Pareto fit.

Revival requires hundreds of homogeneous tail observations, threshold
stability diagnostics, and held-out improvement over an empirical statistic or
block bootstrap.

### Rasch/item-response theory

The present data do not form a crossed respondent-by-item matrix with local
independence and one latent trait. Seeds are not respondents, and three model
sizes supply little ability variation. A mixed-effects logistic model is the
more natural first analysis if a real multi-model benchmark is collected.

**The council study supplies the missing shape, and confirms the objection.**
Three members over sixteen propositions is a genuine crossed 3x16 matrix with
graded responses, which the all-`No` binary data never was. It is still not
enough: all three members scored identically at 8/16, so there is **zero
ability variation to estimate** — the exact degeneracy that makes a Rasch fit
unidentifiable. The members are also two Coder-family sizes plus one Qwen3,
so local independence fails through shared pretraining. Shape is not power.

### CUSUM and Page–Hinkley

A change-point statistic is not literally a mean: temporal order can contain
information the mean destroys. But token margins are syntactically
nonstationary, autocorrelated, and heteroscedastic, so the proposed Gaussian
single-shift model and its calibration are unsupported.

Revival requires blinded fork labels, matched reply structure, separate
calibration/holdout sets, above-chance AUC with uncertainty, and alarms before
the first false token at a fixed false-alarm rate. Repetition degeneration is a
more plausible use than truth gating.

### Doob belief paths

A Doob martingale is `P(E | F_t)` for one fixed terminal event under the same
stochastic generation law. Appending a new yes/no probe defines a different
process, and a greedy path is selected rather than averaged. The proposed
drift and quadratic-variation interpretations therefore do not follow.

A cheap before/after comparison may be called a **self-conditioning probe**.
A genuine martingale study would require calibrated nested rollouts over
sampled outer trajectories and is not a Research C product mechanism.

### Remaining metaphors

Active inference/free energy, tensor networks, quantum walks, Rényi entropy,
Kelly sizing, and a sheaf-cohomology scalar currently make no distinct
validated prediction that changes a release decision. They remain research
metaphors until a bounded experiment separates them from the simpler baselines
above.

