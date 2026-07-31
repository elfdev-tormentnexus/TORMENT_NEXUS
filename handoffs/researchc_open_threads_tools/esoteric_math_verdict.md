# Adversarial ruling on the esoteric-math proposals

Critic agent output, unedited. Winner: coding-rate M2, manifest as a channel.

# ADVERSARIAL RULING

## Set 1 (info-geometry)

**P1 — Pivotal Fisher Information — WEAK (near-dead as specified).**
The Fisher weight is not decoration, it is mis-signed. `I_t = Δ²·s(1−s)` with `s=σ(−Δ)` is *zero at Δ=0* and peaks at Δ≈2.4 nats (I≈0.449). Concretely: a near coin-flip fork at Δ=0.2 scores I=0.0099; a near-committed token at Δ=2.4 scores 0.449 — **45× more weight on the less fragile branch**, inside the retained window. A perfect tie — the maximally pivotal fork — scores exactly 0. The pruning rule at Δ<2.5 hides only the far tail, not the inversion. Everything of value lives in `π_t` (force runner-up, continue, checker-label), which is a pivotality census with no geometry in it; multiply by 1 instead of `I_t` and it is strictly better. Second defect: the headline test is exact McNemar against **mean-entropy thresholding**, already dead by finding 1 — beating a corpse is not evidence. Third: ~480 forced continuations plus slot save/restore is a day of engineering to reach a statistic Set 4 M1 approximates from free logprobs.

**P2 — Contextual Fisher–Rao influence profile — WEAK.**
Methodologically the cleanest thing here: byte-identical forced string across M+/M−/M~ holds register constant by construction, same tokenizer restores the per-position correspondence that killed the embedding idea, and the Bhattacharyya-angle coarse-graining bound is genuinely truncation-safe. But the value is thin. 8/8 exact agreement with a specific 4-digit directory total already makes transcription near-certain; `T` re-confirms it. `PR/L` and `Δ̄` are descriptive layers you would not act on. Its one load-bearing element — the digit-substitution counterfactual (4,356→7,731) — costs six queries and needs no Fisher–Rao at all. Salvage that; discard the rest. Folded into the winner below as a pre-flight gate.

## Set 2 (order-lattice)

**M1 — Filter violation over the entailment poset — WEAK.**
Not refuted: it reads binary answers only, so findings 1–2 are silent, and the use of finding 3 as a *licence* for across-context composition is the single best argumentative move in all eight proposals. But: (i) "entailment" is natural-language entailment as parsed by a 4B abliterated model — a "no" to c2 may be a lexical reading of "defines a class named X", not an incoherence, and there is no paraphrase control anywhere in the design; (ii) 50 edges × 4 cells × hand-written claim templates × AST ground truth per claim is a day-plus of authoring, not the 45 min of compute quoted; (iii) the payoff is taxonomy. "No functioning K-axiom" changes no intervention, and finding 4 at 80/80 already makes it the strong prior. The only genuinely new arm is within-response vs across-context, which is ~10% of the cost — build that alone if you build any of it.

**M2 — Dutch book + stochastic dominance over the containment lattice — LIVE.**
Strongest rebuttal to finding 1 in the batch, and it is correct: `V` and `D` are **invariant to any monotone recalibration applied uniformly to all q**, so they are the formal opposite of a confidence threshold — all-`{0,1}` beliefs can score V=1.0, all-0.5 beliefs score V=0. Needs no ground truth for the coherence half. 288 single-token cells on a frozen prefix is minutes of compute and an afternoon of code. The resolution count (distinct implied medians along a 4-node chain, against a true 4) turns finding 5's anecdote into a number. Real risk they did name: yes-bias and preamble tokens; add a GBNF grammar `root ::= "Yes"|"No"` rather than relying on the <5% discard gate.

## Set 3 (stochastic-process)

**M1 — Step-and-Trough (GLR + Page-Hinkley on top-2 margin) — DEAD.**
Entropy thresholding in disguise, finding 1. `m_t` is a per-token confidence signal; `G_T` is built from `x̄_{k+1:T} − x̄_{1:k}`, i.e. a threshold on a **contrast of two windowed means of that same signal**. The defense ("the mean is a nuisance parameter") would hold if a differential prediction were argued — and none is. *Every* reply that answers a question commits somewhere and rises to an entailed plateau; the honest arm has a step too. Their own Kill-3 concedes the trough may be non-differential, and Kill-2 (AUC ≤ 0.65) is the likely outcome. Compounding it, the localization test depends on 40 human annotations of "the semantic commitment token" produced by someone who knows the class label — unblinded subjective labeling smuggled into the one part that isn't confidence aggregation. Salvage exactly one thing: **the independence argument** — 80/80 determinism means repeats give n=1 effective, so independence must come from distinct file targets. That lesson applies to every design here and is the most useful sentence in Set 3.

**M2 — Doob answer-martingale — WEAK.**
Highest concept, wrong price. S1 is confounded: under greedy decoding you observe one deterministic maximum-probability path, so `E[M_T − M_0] = 0` is not the operative null — the greedy path is systematically selected toward whatever it commits to, and positive drift is guaranteed and uninformative. S2/S3 survive, and the prior-borne vs generation-borne distinction is a genuinely unanswered question with a real fork in the road. But ~9,600 probe calls on one `-np 1` slot plus 320 rollouts, gated on a Spearman computed from 5×8 positions with K=8 binomial noise — an underpowered mandatory kill switch that can fire spuriously and void the whole batch. Decisive objection: **the deliverable is obtainable at 1% of the cost.** Probe `M_0` (before any tokens) and `M_T` (after the full reply) only — 80 calls, five minutes — and `I_0` vs `I_T` already separates prior-borne from generation-borne. The per-position path buys `ρ` and `t*`, which Set 4 M1 localizes from logprobs you are already collecting. Build the 2-point version; do not build this one.

## Set 4 (coding-rate)

**M1 — Bit-price of honesty — LIVE.**
The log-ratio between two tokens at one position cancels the global register factor that made gzip track style — that is the right rebuttal to finding 2, not a hand-wave. Cheap (<15 min compute), ground truth free from AST, and the forced-fork intervention arm is the only within-reply *causal* test proposed. One real hole: `H` is hand-picked, so when the honest continuation opens with a token outside it (" Looking", " Actually", " The"), `B_t` is censored — and `t* = argmin` over a censored set is not well defined. Their "one-sided, bounds suffice" argument licenses lower-bounding `B_t`, not argmin selection. Fix: define `H` empirically as any top-10 token whose greedy continuation the checker labels honest — at which point it converges on Set 1 P1's `π_t` without the broken Fisher weight. That hybrid is the correct build.

**M2 — Manifest as a channel — LIVE.**
Only proposal whose output is a change you ship. Six codes over the same source, paired by file, exact McNemar. The best falsification in the batch is its worst case: *no code beats the decoder → stop the manifest-redesign program.* A negative that saves a month is worth more than a positive that describes a mechanism. The MI arm is the weak half — plug-in MI at N=24 over 5 classes is badly underpowered even with Miller–Madow — but MI is not load-bearing; per-variant exact-match with paired McNemar carries the whole thing.

---

# RANKING (value/cost) AND WINNER

1. **Set 4 M2** — 2. **Set 2 M2** — 3. **Set 4 M1**.

**Winner: Set 4, Measurement 2 (manifest as a channel).** It beats Set 2 M2 because Set 2 M2's output is a *description* of the belief state — and "resolution ≈ 2" is largely implied by finding 5 already — whereas M2's output is a manifest format you deploy or a program you cancel. It beats Set 4 M1 because M1's causal arm is conditional on a fork existing and on `H` containing the right token, while M2's causal arm changes the input and measures the rate, unconditionally. It is also the lowest-engineering LIVE proposal: six strings and a regex classifier.

Amendments before building: demote the MI/conditional-MI arm to *reported, never gating*; steal Set 3 M1's independence rule (distinct files, not repeats); prepend Set 1 P2's digit substitution as a six-query pre-flight.

---

# IMPLEMENTATION SKETCH

**Pre-flight gate (6 queries, ~10 min including setup).** In v1, edit the `assistant/ui` aggregate 4,356 → 7,731, leave everything else byte-identical, re-ask the 3 files in that directory. If ≥2/3 reported numbers move to 7,731, transcription is causal — proceed. If they stay at 4,356, **stop**: the number is not being read out of the manifest and v2/v3 cannot work.

**Corpus.** 24 files pre-screened so `true_lines(f) ≠ dir_total(dir(f))`, spanning ≥6 directories with ≥3 files each (non-degenerate within-directory permutation blocks) and ~1.5 decades of size. Plus 8 real files deliberately absent from the manifest. Ground truth by `wc -l` + AST at collection time, stored per cell.

**Variants.** v1 current; v2 per-file only, aggregates deleted; v3 aggregates relegated to a trailing block headed "DIRECTORY TOTALS — NOT file line counts"; v4 per-file count repeated adjacent to each filename; v5 unit suffix on every number ("412 lines in this file" / "8,912 lines in this directory"); v6 = v2 + "PARTIAL LISTING; absence is not evidence of nonexistence".

**Collection.** Fixed question wording, frozen system prompt, manifest the only thing that varies. 6 × 32 = 192 trials, batched by variant so the prefix cache invalidates **6 times total**. Plus one duplicate v1 pass (32) as a determinism check — if bit-identical, no replicates anywhere else. 224 trials ≈ 13 min at the pessimistic 3.5 s.

**Classification (pre-registered).** Extract every integer; label EXACT / DIR-TOTAL / OTHER-MANIFEST (record which) / NOVEL / REFUSAL. Multiple integers → take the one syntactically bound to the path; none bound → OTHER by position.

**Primary statistic.** `e_v` = #EXACT of 24. File-paired **exact McNemar**, v1 vs each of v2…v6: discordants `(b,c)`, two-sided exact binomial `b ~ Bin(b+c, 0.5)`, Holm across the 5 comparisons.

**Falsification thresholds.**
- *Aggregate-adjacency hypothesis dies* if v2 fails `b ≥ 6, c = 0` (one-sided exact p = 2⁻⁶ = 0.0156) against v1.
- *Whole program dies* if `max_v e_v − min_v e_v ≤ 2/24` with all Holm-adjusted p > 0.05 → no code beats the decoder; stop manifest formatting, route line counts to a deterministic tool call.
- *Existence channel:* v1 expected ≈1/8 (finding 5's 7/7 denials); v6 must reach ≥6/8 with c=0 to license shipping the disclaimer.
- *Void* if the pre-flight gate fails.

**Reported, never gating:** `I(L;ŷ)`, `I(T_dir;ŷ)`, `I(L;ŷ|T_dir)` with Miller–Madow and 10,000 within-directory-block permutations, explicitly flagged underpowered at N=24.

**Honest fallback** if the pre-flight fails or the program-kill branch fires: stop trying to make the director report numbers at all — compute them and inject the answer — and spend the remaining effort only on the existence channel (v6), the one failure mode a prompt-side disclaimer could plausibly repair.

---

# CORRECTIONS TO THE ABOVE (Codex, 2026-07-30) — the ruling is WRONG on two points

Kept unedited above for provenance. Both corrections were verified and accepted.

1. **"Mis-signed" Fisher weight — WRONG.** `I = D^2 s(1-s)` is *valid* Fisher
   information with respect to inverse temperature: with s(b) = sigmoid(-b*D),
   ds/db = -D s(1-s), so I(b) = (ds/db)^2 / (s(1-s)) = D^2 s(1-s). It is
   correctly zero at a tie, because at D=0 both logits are equal and rescaling
   them changes nothing. There is no sign error. The real objection is that
   inverse temperature is the wrong PARAMETER for pivotality. For an additive
   logit perturbation (D -> D + theta), I(theta) = s(1-s), which is maximal at
   the tie -- that is the quantity pivotality wants.

2. **Dutch-book recalibration invariance — OVERCLAIMED.** A monotone transform
   of all q preserves the order relations, so the *set* of ordering violations
   is invariant. The proposed magnitudes V and D are built from the probability
   values themselves and are NOT invariant. Only the violation count survives.

Also note: these proposals were generated by agents explicitly instructed not to
read this repository, to save tokens. They therefore do not know what researchC
already ships. The "honest fallback" the ruling recommends -- compute the
numbers in trusted code and inject the answer -- is ALREADY IMPLEMENTED at
assistant/core/source_awareness.py:389, and an offline weighted rate-distortion
frontier already exists at tools/researchc_report.py:210. Cost every proposal
against the current tree before believing its novelty.

Design corrections required before any 224-trial batch: encodings confound
information content with formatting (deleting aggregates is a RATE change, not
a layout change); rate must be recorded alongside error as a Pareto frontier;
both per-file and aggregate queries need declared weights; and the b=6,c=0
threshold FAILS Holm over five comparisons (one-sided 0.5^6 = 0.0156 > 0.05/5 =
0.01) -- use b >= 8, c = 0 two-sided.
