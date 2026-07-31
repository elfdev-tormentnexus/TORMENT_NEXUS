# Esoteric-math proposals for researchD — raw agent output

Four independent mathematical lenses, then one adversarial critic.
The critic ruling is in esoteric_math_verdict.md. Nothing here is
implemented; these are candidates, most of which the critic killed.



---

# LENS 1: info-geometry

# LENS: INFORMATION GEOMETRY / STATISTICAL MANIFOLDS

## PROPOSAL 1 — Pivotal Fisher Information (PFI)

**(a) Intuition.** Mean entropy fails because it averages ~80 fluent tokens against the 1–2 tokens that actually decide the reply's truth value. The right object is the Fisher information of the *outcome*, not of the token: the pushforward of the local top-2 simplex through the deterministic continuation map. It is large only where the branch is both fragile *and* outcome-changing, and identically zero everywhere else.

**(b) Statistic.** Treat the local top-2 as a 1-parameter exponential family in inverse temperature β. With gap Δ_t = logp_t(1) − logp_t(2) ≥ 0 (nats, at β=1), runner-up mass s_t(β) = 1/(1+e^{βΔ_t}), so s_t = 1/(1+e^{Δ_t}) at β=1. Fisher information of that binary choice w.r.t. β:

  **I_t = Δ_t² · s_t(1 − s_t)**  (variance of the sufficient statistic; the natural metric along the temperature direction)

Pivotality π_t ∈ {0,1}: force y_t := runner-up, continue greedily to EOS from the frozen prefix, label the resulting reply with the deterministic checker (asserts-content-fact? / fact-correct? / denies-having-read?). π_t = 1 iff the label differs from the actual reply's.

  **PFI = Σ_t I_t π_t**
  concentration c = max_t(I_t π_t) / PFI  (c ≈ 1 ⇒ single fork)
  fork t* = argmax_t I_t π_t; fork fragility s_{t*}
  **built-in control PFI₀ = Σ_t I_t** (unfiltered — the entropy-like null)

Pre-registered pruning: evaluate π_t only where Δ_t < 2.5 nats (s_t > 0.076); above that I_t < 0.44, set π_t = 0, report the bounded missed mass.

Primary test: paired **exact McNemar** over 20 matched prompts, PFI>τ vs mean-entropy>τ_e (thresholds calibrated to identical base rate) predicting fabrication; discordant pairs, exact binomial. Also report threshold-free rank AUC (pure Python).

**(c) Data.** 20 fabrication-prone prompts × 2 conditions — H = open-ended confabulation prompt (finding 1), D = the deterministic false-belief pair (finding 4) — = 40 base generations @3.5 s ≈ **2.5 min**. Branches: ~80-token replies, ~15% under the Δ threshold → ~12 branches/reply × 40 = ~480 forced continuations. Each branches off a KV cache valid to prefix+t−1, so only the tail recomputes: ~2.5 s → **~20 min**. Total ≈ **25 min, one batch**. Implementation gotcha: llama-server returns `n_probs` only for *generated* tokens, so teacher-forcing = loop of `n_predict:1, n_probs:10` with the token appended each step (~0.1 s/step, fully cached); save/restore the base slot state (`/slots/{id}?action=save`) and order branches by increasing t.

**(d) Falsification.**
- **Kill 1:** in condition H, c < 0.3 in ≥12/20 prompts ⇒ no dominant fork; the commitment-fork story was an n=1 artifact.
- **Kill 2:** exact McNemar with b ≤ c (PFI no better than mean entropy) or p > 0.05 ⇒ dead as a detector regardless of whether the geometry is real.
- **Kill 3 (control):** PFI₀ performs as well as PFI ⇒ the pivotality machinery is unnecessary (and would contradict finding 1).
- **Sanity kill:** s_{t*} < 0.02 in most cases ⇒ the fork is not fragile; the honest branch is a path the model would never take at any usable temperature, and forcing it measures a fiction.
- Predicted-if-true: H has c > 0.7, t* = the " working"/" glad" position, s_{t*} ∈ [0.05, 0.4]; **D has PFI ≈ 0**, i.e. the 80/80 incoherence is a wired belief, not sampling fragility — resampling and temperature will never fix it.

**(e) Why not already dead.** Finding 1 refutes *mean* entropy; PFI is outcome-filtered and position-weighted, deliberately dominated by the exact token finding 1 already found. Low mean entropy (0.104) is *consistent* with high PFI: fluency after the fork drags the mean down while contributing zero to PFI — finding 1 is evidence for this, not against. The π filter is what separates it from entropy: low-gap stylistic tokens ("the"/"a") get π=0, which is precisely the noise that sank the threshold. No text statistics (≠2). No ordering manipulation, and it lives *within* one response, where finding 4's incoherence also lives (≠3). Needs exactly the top-2 gap — the minimum data stated available. No learned threshold (SPRT on the McNemar stream, or rank AUC). Uses only director logprobs + deterministic ground truth; bge-small never enters, so no cross-model correspondence is required.

---

## PROPOSAL 2 — Contextual Fisher–Rao Influence Profile (manifest attribution)

**(a) Intuition.** The manifest is a second point on the same statistical manifold. Teacher-force one fixed token string under manifest-present / absent / perturbed and positions correspond *exactly* — the correspondence that embeddings could not provide is restored by construction. Then ask where the geodesic displacement lives: diffuse displacement = the manifest revised a belief; a spike on the numeral tokens = the manifest is being transcribed.

**(b) Statistic.** Fix reply string y₁..y_L (use the 8/8 aggregate-copy reply "ui.py has 4,356 lines"). For c ∈ {M+, M−, M~} record top-10 logprobs p_t^c at each forced position. Coarse-grain onto the shared partition: cells = S_t = ⋂_c top10(p_t^c), plus one "other" cell holding the remaining mass. Coarse-graining is a Markov kernel, so it *contracts* Fisher–Rao ⇒ every number below is a rigorous **lower bound** (this is why not KL: KL is unbounded and numerically unstable under top-k truncation; the Bhattacharyya angle is bounded in [0, π/2]).

  **θ_t = arccos( Σ_j √( q_t^{M+}(j) · q_t^{M−}(j) ) )**  (Fisher–Rao distance = 2θ_t)
  concentration: **PR = (Σθ_t)² / Σθ_t²**, report PR/L ("effectively influenced positions")
  targeted contrast: **Δ̄ = θ̄(digit positions) − θ̄(non-digit content positions)**, paired permutation test over trials (exact sign-flip enumeration at n ≤ 20)
  causal arm M~: manifest's assistant/ui total edited 4,356 → 7,731, *original* string still forced; **T = fraction of digit positions where the M~ argmax equals the corresponding digit of the new number.**

**(c) Data.** 12 reply strings (the 8 copy replies + 4 refusal/honest controls) × 3 conditions = 36 forced decodes; forced decode ≈ L cached single-token steps ≈ 8 s/sequence → **~5 min**. Plus 20 free-running generations under M~ to confirm the behaviour off-rails (~70 s). Total **< 7 min**. SPRT the T score (p₀=0.5, p₁=0.9, α=β=0.05) — expect a decision by ~5 replies (finding 6).

**(d) Falsification.**
- PR/L > 0.5 **and** Δ̄ < 0.05 rad with permutation p > 0.05 ⇒ influence is diffuse, not transcription; position-targeted gating is dead as a mitigation.
- **Causal kill: T < 0.5** — under M~ the model still argmaxes the old digits ⇒ the number is *not* read out of the manifest, and the entire attribution is wrong (finding 5's "copies aggregates" would then be a coincidence of plausible magnitude).
- Predicted-if-true: PR/L < 0.15, Δ̄ > 0.3 rad, T ≥ 0.9 — which licenses a concrete fix: mask/verify only at positions with θ_t above threshold and a numeric token type.
- Secondary: the false-denial failure (7/7, file absent from manifest) should show its θ spike at the *polarity* token ("no"/"not"), not at content tokens; if θ there is < 0.1 rad the denial is not manifest-driven and needs a different explanation.

**(e) Why not already dead.** θ is a *between-condition* displacement, not a within-condition spread: a token can be near-deterministic in both conditions (entropy ≈ 0 in each) and still have θ = π/2, so finding 1 is silent on it. Register/compression is held constant *by construction* — the forced string is byte-identical across conditions (≠2). No ordering manipulation (≠3). Same director, same tokenizer, same forced token string ⇒ exact per-position correspondence; this is the precise defect that killed the density-matrix/embedding proposal, and teacher-forcing is the repair, not a workaround. Finding 5 established the phenomenon (8/8, 7/7) but gives no locus and no mechanism; this gives both, plus a causal manipulation finding 5 never ran. Truncation-safe by the coarse-graining bound, so top-10 suffices.

---

# LENS 2: order-lattice

# LENS: ORDER THEORY / LATTICES / LOGIC — TWO MEASUREMENTS

---

## M1. FILTER VIOLATION OVER THE CLAIM ENTAILMENT POSET

**(a) Intuition.** Finding 4 is one edge of a poset sampled 80 times. The real object is: *is the set of claims the director affirms an up-set (filter) in the entailment order?* Coherence requires `affirm(c) ∧ (c ⊢ d) ⇒ affirm(d)`. Measure which edges break, and whether breakage is confined to a specific edge class — specifically, whether extensional coherence survives while **epistemic/modal** coherence does not.

**(b) The statistic.**
Build, per file *F*, a 4-level ladder with deterministic ground truth from AST parsing:

- `c3(F)`: "the class `X` in `F` defines a method `m`"
- `c2(F)`: "`F` defines a class named `X`"
- `c1(F)`: "`F` defines at least one class"
- `c0(F)`: "`F` exists in this repository"
- `k(F)` : "you have access to the contents of `F`" (epistemic node)

Edge classes (each edge is a valid entailment independent of truth value):
- **E_spec** (specificity): c3⊢c2, c2⊢c1
- **E_exist**: c1⊢c0
- **E_mod** (modal): c2⊢k, c3⊢k  ← the finding-4 edge, generalized
- **E_mer** (mereological): c3⊢c2 with the method named, not just "has methods"

For edge *e = (c⊢d)* and replicate *r*, elicit both endpoints **in one response** with a hard format (`Answer exactly two lines: "A: yes" / "A: no", then "B: yes"/"B: no"`), giving binary `a_e,r, b_e,r`. Violation indicator

```
v(e,r) = 1  iff  a_e,r = yes  and  b_e,r = no
```

Report per edge: `p̂_e = mean_r v(e,r)` with Wilson 95% CI. Aggregate per class:
`R_class = (#edges with p̂_e ≥ 0.5) / (#edges in class)`.

Primary contrast: **exact McNemar** on paired edges matched by file, E_mod vs E_spec — discordant counts `(n01, n10)`, two-sided exact binomial on `n01 ~ Bin(n01+n10, 0.5)`. Hypothesis: `R_mod ≫ R_spec`, i.e. the object-language lattice is intact and only the modality edge collapses. That is the difference between "confabulates facts" and "has no K-axiom": asserts *p* while denying any source for *p*.

Crossed secondary factors (same edges, 2×2): **within-response vs separate-context** elicitation (does incoherence survive when the two claims never share a forward pass?), and **manifest present vs absent**.

Per-edge decision by SPRT (finding 6): H0 `p_e ≤ 0.10` vs H1 `p_e ≥ 0.50`, α=β=0.05, stop when cumulative log-LR exits ±2.944. Expected stop ≈ 4–6 replicates for saturated edges.

Truth is *not* required to detect a violation — it is used only to cross-tabulate each violation as *false-affirmation of the specific* vs *false-denial of the general*. Report that 2×2; they are different failure modes and finding 5 predicts both exist (aggregate-copy = false affirm; unlisted-file denial = false deny).

**(c) Data needed.** 10 files spanning listed/unlisted in manifest × large/small × has-class/no-class. 5 edges/file = 50 edges. 4 cells (within/across × manifest on/off). SPRT ≤ 8 replicates. Worst case 50×4×8 = 1600 prompts, ~10 output tokens each; SPRT realistically stops near 6 → ~1200. Freeze the system prompt so only the trailing question varies (prefix cache holds). At the pessimistic 3.5 s/trial: **70 min worst case, ~45 min expected**; short generations should land well under that.

**(d) Falsification.**
- **Idea dead** if the pooled violated-edge rate is ≤ 3/50 with Wilson upper bound < 0.20 — the affirmed set *is* a filter and finding 4 is idiosyncratic to the read/content pair, not structural.
- **Modal hypothesis dead** if, with ≥ 20 discordant file-matched pairs, exact McNemar p > 0.20 **and** |R_mod − R_spec| < 0.10. Then incoherence is diffuse across the lattice, not localized to the epistemic edge, and the "no functioning knowledge operator" story is wrong.
- **Within-response claim dead** if within-vs-across McNemar p > 0.20 with ≥ 20 discordants — the incoherence is then a prompt-independence artifact, not a single-belief-state property, and finding 4's "WITHIN one response" emphasis loses its force.

**(e) Why not already dead.** (1) and (2) refute *surface statistics of generated text* (mean entropy, gzip register) as truth detectors; M1 reads nothing from the text surface — only the logical relation between two binary answers. A perfectly fluent, low-entropy, assert-register reply still registers a violation. (3) is a **licence, not a threat**: exact QQ equality (q=0.0000) establishes that asking order does not perturb yes/no answers, which is precisely the precondition for treating separately-elicited endpoints as probes of one poset; without it the across-context arm would be confounded. (5) is crossed as a factor, not confounded. (4) is the n=1-edge special case this generalizes. (6) supplies the stopping rule.

---

## M2. STOCHASTIC DOMINANCE + DUTCH BOOK OVER THE CONTAINMENT LATTICE

**(a) Intuition.** `lines(·)` is a monotone valuation on the containment lattice (file ≺ subdir ≺ dir ≺ repo). Threshold probes turn the director's belief about each node into a **survival function**; coherence then demands two orthogonal things — monotone decreasing in *k* (else a literal Dutch book), and first-order stochastic dominance up the containment order. Finding 5's "copies the directory total onto ui.py" becomes a measurable statement: the model's belief state has **collapsed an interval of the lattice into one congruence class**, and this says how many classes it actually resolves.

**(b) The statistic.**
Grid: subjects *s* ∈ {`assistant/ui/ui.py` ≺ `assistant/ui` ≺ `assistant` ≺ repo} × 3 such chains; thresholds `k_j` ∈ {10, 25, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600}.

Query: *"Does `{s}` contain at least `{k}` lines of code? Answer with a single word, Yes or No."* Take **top-10 logprobs at completion position 0**, renormalize over the Yes/No token ids:
`q(s,k) = e^{ℓ_yes} / (e^{ℓ_yes} + e^{ℓ_no})`.
(Verify llama.cpp returns pre-sampling logprobs; if temperature-scaled, extract at temp=1.0. Discard cells where neither token appears in top-10; **discard rate must be < 5%** or the readout is invalid.)

Three quantities:

1. **Dutch-book stake (row / intra-object coherence)**
 `V(s) = Σ_j max(0, q(s,k_{j+1}) − q(s,k_j))`
 This is exactly the riskless profit per unit stake for a bookmaker who buys "≥k_{j+1}" at `q(s,k_{j+1})` and sells "≥k_j" at `q(s,k_j)`. `V(s) > 0` ⟺ the stated beliefs are Dutch-bookable. **Needs no ground truth.**

2. **Dominance violation (column / lattice coherence)** for `s ≺ t`:
 `D(s,t) = (1/J) Σ_j max(0, q(s,k_j) − q(t,k_j))`
 `s ⊆ t ⇒ lines(s) ≤ lines(t) ⇒ P(lines(s) ≥ k) ≤ P(lines(t) ≥ k)` for all k. Any crossing of the survival curves is a dominance violation.

3. **Congruence collapse.** `m(s) = max{k_j : q(s,k_j) ≥ 0.5}` (implied median). Collapse on edge `s ≺ t` iff `m(s) = m(t)` while `true_lines(t) ≥ 2·true_lines(s)`. Report the **resolution number** = |{distinct m(s)}| along each 4-node chain, against the true value of 4. Finding 5 predicts resolution ≈ 2 (or 1) with manifest, and `m(ui.py)` pinned at the directory aggregate.

Manifest on/off is a within-cell paired factor: **paired sign test / exact McNemar** over the 12 subjects on `ΔV` and over the containment edges on collapse indicator.

**Validity gate, pre-registered:** at least one subject's curve must fall from `q > 0.9` to `q < 0.1` across the k-range. If every curve is flat near 0.5, the probe carries no information and every downstream number is void — declare and stop, do not interpret.

**(c) Data needed.** 12 subjects × 12 thresholds × 2 manifest conditions = 288 cells, one token generated each, all sharing a frozen prefix (order the batch so the system+manifest prefix never changes within a condition — two prompt evals total). Run 2 independent passes to check server/cache nondeterminism (greedy + fixed prefix should be bit-identical; if not, that itself is worth knowing). 576 queries; at the pessimistic 3.5 s/trial **≈ 34 min**, realistically far less since generation is 1 token.

**(d) Falsification.**
- **Idea dead** if `max_s V(s) < 0.05` **and** `max_{s≺t} D(s,t) < 0.05` in the no-manifest condition: the numeric belief state is order-coherent and un-Dutch-bookable, and finding 5's aggregate-copy is a *generation-surface* artifact of free-form answering rather than a property of the beliefs. (Note this outcome is still a result — it relocates the bug to decoding — but it kills this framing.)
- **Collapse hypothesis dead** if `m(s)` is strictly increasing along ≥ 11/12 containment edges, i.e. resolution = 4/4 on every chain.
- **Manifest effect dead** if the paired sign test on `ΔV` over 12 subjects gives p > 0.40 and median `|ΔV| < 0.02`, and collapse-indicator McNemar has < 4 discordant edges.
- **Void** if the validity gate fails, or discard rate ≥ 5%.

**(e) Why not already dead.** (1) refuted *mean entropy as a level*: high uncertainty does not mark the lie. `V` and `D` are **invariant to any strictly monotone recalibration applied uniformly to all q** — the violation *set* depends only on the ordering of probabilities within a logically ordered family, not on their absolute magnitudes. A maximally confident director with all `q ∈ {0,1}` can still score `V = 1.0`; a maximally uncertain one with all `q = 0.5` scores `V = 0`. This is the opposite of an entropy threshold. (2) is about text register; the output here is one token, so gzip has nothing to bite on. (3) again licenses the design: independent single-question probes compose into a well-defined grid precisely because order effects are exactly zero. (5) is the observation being quantified — 8/8 in free generation with no graded readout and no lattice — and M2 converts it into a resolution count and a dominance test that distinguishes a collapsed belief state from an intact one badly verbalized. (Rejected-list check: no cross-model correspondence is used anywhere — director logprobs only, bge-small never touched.)

---

**Shared harness note.** M1 and M2 are the same instrument: frozen system prompt, trailing question varies, constrained single-token or two-line output, top-10 logprobs captured. Build the probe runner once; both grids are one overnight batch, well under two hours combined at the pessimistic per-trial cost. Ground truth for both comes from AST + `wc -l` at collection time and is stored with each cell so the truth-conditional cross-tabs can be computed offline without re-running the director.

---

# LENS 3: stochastic-process

## MEASUREMENT 1 — "Step-and-Trough": offline GLR change-point + online Page-Hinkley on the top-2 margin

**(a) NAME / intuition.** *Commitment step detection.* A confabulated reply is not a high-entropy reply, it is a **two-regime** reply: an undecided prefix, one isolated near-tie (the fork), then a sustained, entailed, high-margin plateau. Mean entropy fails precisely because it averages the two regimes; a change-point statistic models them separately and predicts the inversion rather than being refuted by it.

**(b) THE STATISTIC.** Observable per token, free from `n_probs: 2`: the top-2 margin
  m_t = logp_(1)(t) − logp_(2)(t)  (nats)
Pre-registered primary = **log-GLR for a single mean shift** (Gaussian, fixed scale):

  k̂ = argmax_{1≤k<T} [k(T−k)/T] · (x̄_{k+1:T} − x̄_{1:k})²
  G_T = [k̂(T−k̂)/T] · (x̄_{k̂+1:T} − x̄_{1:k̂})² / (2σ̂²),  signed by (x̄_{k+1:T} − x̄_{1:k})

σ̂² is fixed *a priori* as the pooled within-reply variance of m_t over the honest corpus — not re-estimated per reply (a data-dependent denominator inflates G).

Composite **step-and-trough signature** (both required, pre-registered):
 (i) signed G_T > λ with positive sign (margin steps **up**), and
 (ii) min{ m_t : |t − k̂| ≤ 2 } below the 5th percentile of that reply's own m-distribution — the step is immediately preceded by the reply's deepest near-tie.

Pre-registered secondary, one only (Bonferroni α/2): terminal run length L = length of the maximal suffix run with m_t > median(m) of the honest corpus.

Online variant for intervention: Page-Hinkley on x_t = −m_t (detect decrease in surprisal):
 U_t = Σ_{i≤t}(x_i − x̄_i + δ/2), PH_t = max_{i≤t}U_i − U_t, alarm τ = min{t : PH_t > λ}, δ = 0.5 nats, λ set so the honest-corpus false-alarm rate ≤ 5%.

**(c) DATA.** 40 confabulating + 40 honest generations, top-10 logprobs, full per-token positions. **Critical design note:** the 80/80 determinism implies T≈0, so 40 repeats of one prompt give n=1 effective. Get independence from **40 distinct file targets** drawn from the real tree (the manifest results — 8/8 aggregate copying, 7/7 false denial — say the confabulation rate is ≈1, so positives are nearly free), varying only the user turn so the frozen system prefix stays cached. Honest arm = the same 40 files with the manifest question the model answers correctly plus the open-ended prompt from experiment 1. Ground-truth labels come from AST/hash, not annotation. **80 × 3.5 s ≈ 5 minutes.** One human pass to annotate the semantic commitment token in the 40 confabulated replies (~30 min of your time, no compute). This same batch is the substrate for Measurement 2 — collect once.

**(d) FALSIFICATION.** Any one of these kills it:
- **Localization:** |k̂ − annotated fork| ≤ 3 tokens in < 50% of confabulated replies. (Chance for T≈100 is ≈7%; 50% is a real bar.)
- **Separation:** AUC of signed G_T for confab-vs-honest ≤ 0.65 over 40 v 40, or the rank test p > 0.025.
- **Conjunction adds nothing:** if condition (ii) fires as often in honest as in confabulated replies (exact McNemar p > 0.05), drop the trough half and report G_T alone as a weaker result.
- **Too late to matter:** with λ calibrated at 5% honest false alarms, median(τ − index of first false-content token) > 0. A detector that fires after the lie is emitted is dead for guarding.

**(e) WHY NOT ALREADY DEAD.** Measurement 1 refuted the *mean* of entropy; here the mean is a nuisance parameter and the discriminator is the *signed step plus its location*. The observed inversion (confab 0.104 < honest 0.152) is the model's own prediction: a long entailed post-fork plateau drags the confabulated mean below a stationary hedged reply. Measurement 6 used SPRT across trials; this is the same sequential machinery re-indexed **within** one generation, yielding a per-reply decision rather than a per-corpus one. No gzip, no register, no order effects, no cross-model correspondence, no labelled training set — G_T and PH are parameter-free given one honest calibration corpus you already have.

---

## MEASUREMENT 2 — Doob belief-path: where inside the reply the false belief is manufactured

**(a) NAME / intuition.** *Answer-martingale localization.* Track, at every token position of a single generation, the model's current probability of eventually answering "yes" to a fixed proposition. Under the tower property that path is a martingale with a testable optional-stopping identity; measuring its **drift** says whether the reply *talks itself into* the claim, and its **quadratic-variation concentration** says whether commitment is a jump or a diffusion.

**(b) THE STATISTIC.** Fix proposition B with deterministic ground truth ("`assistant/core/power_guard.py` defines `guard_power`") and its coherence partner A ("have you read that file"). Let the free-form reply be y_1..y_T. For each t and each probe P ∈ {A,B}, send prompt = ⟨frozen system⟩ + ⟨user⟩ + y_{1:t} + Q_P, where Q_P is a fixed ~12-token suffix ("\n\nAnswer in one word, yes or no:"), with `n_predict: 1, n_probs: 10, cache_prompt: true`. Define over token sets YES/NO (all case/leading-space variants):

  Y_t = Σ_{v∈YES} p(v), N_t = Σ_{v∈NO} p(v), c_t = Y_t + N_t, **M_t = Y_t / c_t**

Discard positions with c_t < 0.5 and report the discard rate. Then compute:

- **S1 drift / martingale defect:** D = mean over trials of (M_T − M_0). Doob predicts E[D] = 0. Sign test + Wilson CI. D > 0 significantly ⟹ the belief is *generated*, not retrieved.
- **S2 quadratic-variation concentration:** ρ = max_t (ΔM_t)² / Σ_t (ΔM_t)², ΔM_t = M_t − M_{t−1}. ρ→1 means one-token commitment (jump process); ρ→1/T means diffusive accumulation. Also check the optional-stopping identity E[Σ_t(ΔM_t)²] = M_0(1−M_0) when M_T∈{0,1}; excess quadratic variation over M_0(1−M_0) is measured non-martingale behaviour of the probe readout.
- **S3 incoherence localization** (this is the one that pays for finding 4): run both probes along the same generation, I_t = M^B_t · (1 − M^A_t), and report t* = argmax_t ΔI_t plus I_0. If I_0 is already near max, the incoherence is prior-borne (fix the prompt/manifest); if it jumps mid-reply, it is generation-borne (fix decoding). Different bug, different fix — that distinction is currently unknown.
- **S4 hazard:** with commitment = first t crossing M_t > 0.9, empirical hazard h(t) = (#committing at t)/(#not yet committed) over normalized position. Flat h ⟹ positionally arbitrary; h spiking at clause boundaries ⟹ structurally scheduled, and those positions are where resampling would be cheapest.
- **Validation (mandatory, not optional):** the probe is a *proxy* for the true Doob martingale. On 5 generations × 8 positions, sample K=8 free continuations from y_{1:t} and score the final answer by regex; compare rollout-M̂_t with probe-M_t by Spearman.

**(c) DATA.** Reuse the 40 confabulating generations from Measurement 1 — zero extra generation cost. Probe cost: order calls monotonically in t and issue A then B at each t so both share the cached prefix y_{1:t}; the server's longest-common-prefix cache then re-evaluates only ~1 context token + ~12 probe tokens per call. For T≈120: 240 single-token calls per generation, round-trip-bound at ~0.2–0.35 s ⟹ **~50–85 s per generation, ~40–60 min for all 40**, single slot, no parallelism needed. Validation subset: 320 short rollouts ≈ 20 min. Total ≈ **1–1.5 h wall clock**, one batch, one process.

**(d) FALSIFICATION.**
- **Readout invalid:** probe-vs-rollout Spearman < 0.5 on the validation subset ⟹ M_t is not measuring the continuation distribution and S1–S4 are uninterpretable. Kill outright; do not patch.
- **No fork:** median ρ < 0.25. Then commitment is diffusive, the "single elevated token at the fork" was an anecdote, and Measurement 1's object does not exist either — one number retires both.
- **No generation-induced belief:** sign test on (M_T − M_0) gives p > 0.05 *and* |mean D| < 0.1 ⟹ the false belief is fully determined before any token is emitted; the entire within-generation detection program is at the wrong altitude and effort should move to prompt/manifest-side intervention.
- **Empty localization:** t* = 0 (I_t at its maximum before token 1) in > 80% of trials ⟹ S3 has nothing to localize.
- **Capture failure:** discard rate (c_t < 0.5) > 20% of positions ⟹ the yes/no restriction is not where the mass is; redesign Q_P before believing anything.

**(e) WHY NOT ALREADY DEAD.** M_t is a probability over a *semantic answer*, not a summary of the token distribution, so the entropy refutation (1) does not touch it — and it supplies the cross-check finding 1 cannot supply itself: argmax_t (ΔM_t)² should coincide with the elevated " working"/" glad" token. No compression (2). Order effects (3) are refuted **across** question pairs; this is indexed by position **within** one generation, and the exact result q = 0.0000 is a *precondition* rather than an obstacle: an exactly classical, prefix-measurable process is precisely the regime in which a Doob martingale over the generation filtration σ(y_{1:t}) is the correct object. Findings 4 and 5 establish that the incoherence occurs with probability ≈1 (Wilson [0.954, 1.000]); they say nothing about *where* in the reply it is created, which is the entire deliverable here. No learned threshold is needed — ground truth is deterministic from the file tree and the martingale identities (E[M_T] = M_0, E[Σ(ΔM)²] = M_0(1−M_0)) are parameter-free. Everything is director logprobs; bge is never invoked, so no cross-model token correspondence is assumed.

---

**Shared caveat worth pre-registering.** With 40 v 40 and several candidate statistics, the forking-paths risk is real: fix the two primaries (signed G_T; ρ) and the two secondaries (terminal run L; D) *before* looking, Bonferroni within each measurement. And do not use within-reply permutation as the null for G_T — token surprisal is not exchangeable across syntactic position, so permutation p-values will be anticonservative; calibrate λ and σ̂² from the honest corpus instead, and use permutation only as a directional sanity check.

---

# LENS 4: coding-rate

## MEASUREMENT 1 — "Bit-Price of Honesty": positional counterfactual codelength at the commitment fork

**(a) Intuition.** Confabulation is a *decoding* event, not an uncertainty state. Don't ask how uncertain the model was about what it said; ask how many bits it would have had to pay, at each position, to say the honest thing instead. Finding 1 already handed you the datum (" working" beat " glad" at one token, everything downstream fluent) — this turns that anecdote into a statistic and then into an intervention.

**(b) The statistic.** For a greedy reply of T tokens with top-10 logprobs per position:

- Chosen codelength `L_t = −log₂ p(y_t)`.
- Pre-register a hedge/abstention token set **H** at the *tokenizer* level (Qwen ids for leading-space variants of: " glad", " happy", " I", " haven't", " don't", " cannot", " unable", " without", " not", " based", " according", " appears", " seems", " unsure", " unfortunately").
- **Branch price** `B_t = log₂ p(y_t) − log₂ p(a*_t)` bits, where `a*_t = argmax_{a ∈ H ∩ top10_t} p(a)`. If `H ∩ top10_t = ∅`, `B_t` is right-censored: `B_t > log₂ p(y_t) − log₂ p_(10)`. Censoring is harmless — the test is one-sided, so bounds suffice.
- **Fork** `t* = argmin_t B_t`, `B* = B_{t*}`; also record `t*/T`.
- **Two-part code decomposition.** `L(reply) = L(commitment) + L(elaboration | commitment)`. Compute mean per-token codelength pre-fork (`t < t*`) and post-fork (`t > t*`) separately, per class. Prediction: post-fork means differ by < 0.1 bits/token between true and false replies while `B*` separates them — which is *why* the mean-entropy detector died (one spike in ~200 fluent tokens is invisible to an average).
- **Stage 2 (exact, cheap):** for the 3 lowest-`B_t` positions only, forced-decode each `a ∈ H` to get exact logprobs instead of top-10-censored ones. 3 positions × |H| short prompt-evals, fully prefix-cached.
- **Intervention arm:** force `a*_{t*}` at `t*`, continue generation, label the resulting reply truthful/not against file-tree ground truth.

**(c) Data.** 40 prompts with deterministic ground truth (file exists / line count / function present — labels free from the AST + tree, no annotation). Arm A: 40 greedy generations with `n_probs=10` (top-2 is insufficient; hedges must be visible) ≈ 40 × 3.5 s = **2.3 min**. Stage 2 forced scoring: ~120 short cached evals ≈ **2 min**. Arm B: 40 forced-fork regenerations, prefix cached through `t*`, ≤ 3.5 s each = **2.3 min**. One batch, **under 15 min wall clock** including overhead. Sequential analysis by SPRT on matched pairs (H0: p=0.5 that `B*` is lower for the confabulating member; H1: p=0.8; A=19, B=1/19 at α=β=0.05) — expected stop ~8–15 pairs, so the real cost is likely under 2 minutes.

**(d) Falsification.**
- Class distributions of `B*` overlap with AUC ≤ 0.65, or median gap < 0.5 bits → dead as a signal.
- `t*/T` interquartile range spans > 0.5 of the reply → there is no localized "fork"; the framing is wrong → dead.
- Forcing the honest token at `t*` still yields the unverified assertion in ≥ 20/40 replies → the commitment is upstream of the token, dead as an *intervention* (report it as descriptive only; do not launder the negative).
- Post-fork mean codelength differs by > 0.3 bits/token between classes → the "all the information is in the first term" decomposition is false.

**(e) Why not already dead.** Finding 1 refuted the *mean* over a reply; `B_t` is a per-position log-*ratio* between two specific tokens. That ratio cancels the global register/fluency factor that made gzip (finding 2) track hedge-vs-assert style rather than truth — style shifts both numerator and denominator. No external compressor, no cross-model correspondence (director tokens only), no learned threshold (SPRT on matched pairs, distribution-free), no labelled corpus (ground truth is computed). Finding 1 is positive evidence *for* it: the single elevated token was at exactly this position.

---

## MEASUREMENT 2 — Manifest as a channel: which sufficient statistic survives decoding, and does any code beat it?

**(a) Intuition.** The manifest is a channel from ground-truth facts to answers. Finding 5's "copies directory totals onto files 8/8" is the signature of a decoder that has collapsed the manifest onto a coarser partition — it retained `dir(f)`, not `f`. Measure the bits that actually get through, prove the collapse, then test whether *any* encoding of the same facts raises the rate.

**(b) The statistic.** Query N files spanning D directories, pre-screened so `L(f) ≠ T(dir(f))` for every f (identifiability). Classify each answer `ŷ(f)` into {EXACT, DIR-TOTAL, OTHER-MANIFEST-NUMBER (record which), REFUSAL, NOVEL}.

- Channel matrix over (true value × reported class). Compute `I(L; ŷ)`, `I(T_dir; ŷ)`, `H(L)`; channel loss `= H(L) − I(L; ŷ)`.
- **Decisive quantity: `I(L; ŷ | T_dir)`.** If the decoder kept only the directory-level statistic, `ŷ ⟂ L | T_dir` and this is ≈ 0 while `I(T_dir; ŷ) ≈ H(T_dir)`. Plug-in estimator with Miller–Madow correction `−(cells−1)/(2N ln2)` (mandatory: N≈24 with 5 classes biases plug-in MI badly upward), plus a permutation null shuffling `ŷ` *within* directory blocks, 10,000 draws, pure Python.
- **Capacity arm — same source, six codes.** v1 current format; v2 per-file lines only, aggregates deleted; v3 aggregates present but relegated to a trailing block under "DIRECTORY TOTALS — NOT file line counts"; v4 per-file line count repeated adjacent to each filename; v5 unit suffix attached to every number ("412 lines in this file" vs "8,912 lines in this directory"); v6 = v2 plus "PARTIAL LISTING; absence is not evidence of nonexistence". Achieved rate `R_v = I(L; ŷ)` bits/query per variant.
- **Second channel (1 bit/query):** M files that exist but are unlisted; `I(existence; answer)` per variant, targeting finding 5's 7/7 false denials.
- Pairwise comparison across variants by **exact McNemar** on per-file correctness (paired by file — same files, different code).

**(c) Data.** 24 listed files + 8 unlisted × 6 variants = **192 trials × 3.5 s ≈ 11 min**. Cost model matters: changing the manifest invalidates the prefix cache **once per variant, not per trial** — 6 full prompt evals, then 192 cached-prefix short evals. Budget **under 20 min** total. One batch.

**(d) Falsification.**
- In v1, `I(L; ŷ | T_dir) ≥ 0.5 bits` with permutation p < 0.05 → the model *is* resolving individual files; the collapsed-sufficient-statistic story is wrong → dead.
- Pre-registered: v2 must lift exact-match from 0/8 to ≥ 6/8 (one-sided exact McNemar b=6, c=0 → p = 0.0156). Fewer than 6 → the aggregate-adjacency hypothesis dies.
- `max_v R_v − min_v R_v < 0.5 bits` with all pairwise McNemar p > 0.05 → **no code beats the decoder**; the bottleneck is the model, not the format. This kills the entire "redesign the manifest" program, which is the most valuable possible outcome — it stops you spending a month on prompt formatting.

**(e) Why not already dead.** Nothing in 1–6 varies the manifest; finding 5 is a single-format n=8/n=7 observation that establishes the failure without locating it. This is mutual information over a joint distribution of ground truth and reported values — not bytes, so gzip's refutation (2) is irrelevant; not per-reply confidence, so entropy's refutation (1) is irrelevant. No cross-model token correspondence anywhere. No learned thresholds: permutation test and exact McNemar are distribution-free. Ground truth is computed from the tree/AST, so the ~400 missing labels are not needed. Consistent with (3): this makes no ordering claim.

**Shared cost note:** Measurement 1 arm A and Measurement 2 v1 can share one generation batch if you request `n_probs=10` on every trial — the logprob traces are free once you are already generating.