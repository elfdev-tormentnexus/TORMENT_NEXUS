# Research C controlled-index decoding experiment

Status: **120/120 calls completed; confirmatory batch valid; no production
change licensed.**

This is the full empirical follow-up to the six-call aggregate-substitution
preflight. It tests how one frozen Qwen3-4B director decodes four controlled
source-index encodings. It does not test Sable's trusted source resolver: the
collector calls the one-slot llama-server directly because the product route
correctly answers source questions in Python before generation.

## Binding and validity

- 28 unique questions × 4 cells, plus Q01/Q25 replay sentinels in every cell:
  120 calls.
- Four seven-question groups used a balanced Williams schedule. Every cell
  occupied every temporal position once and every directed carry-over pair
  occurred once.
- Frozen selected-source snapshot:
  `1152b2e12dd5c32fc9957c721461ca7021b93f4c471760312b4c7efc37beee3d`
  (87 files).
- Model:
  `947656a42e73bda324c527f06953596b77e4d91bc590476955205b5f64d4e974`.
- Live server bundle:
  `2cfd58b8b4a2e9a1081cab1168877dfa6598f0c430c6970afbd41a37f08f96ab`.
- The hazard parent, one-slot director, and unpooled machinespirit helper were
  bound to their live processes. Port 8099 was closed. An inert F24 console
  pulse kept Sable's five-minute idle check from racing or shutting down the
  director.
- Zero HTTP failures, retries, source/repository drift, or normalized sentinel
  mismatches. The batch is not descriptive-only.

The independent pre-launch audit changed the preregistration before call one:
the compact schema was made byte-identical between low and high rate, cell
order was Williams-balanced instead of confounded with four time blocks,
dispatch intent became durable before every request, and the interpretation
was narrowed to a greedy channel-decoding experiment. No result below is a
full-tree allocation or deployed-sampler result.

## Cells

`Y` is source reconstruction: did the reply match the real repository?
`S` is support correctness: was the reply licensed by the supplied controlled
index? A lucky `YES` about an omitted real file is Y-correct but S-wrong.

The scores below use the preregistered equal-stratum profile. Other profiles
are preserved in `rate_distortion_summary.json`.

| Cell | Encoding | Manifest tokens | Y | S | File lines exact | Aggregates exact | Listed YES | Unlisted result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| LC | low-rate compact | 614 | 0.4375 | 0.5625 | 0/12 | 3/4 | 8/8 | 2 UNKNOWN, 2 false NO |
| LE | low-rate explicit | 609 | 0.21875 | 0.21875 | 0/12 | 3/4 | 1/8 | 4 false NO |
| HC | high-rate compact | 692 | 0.51042 | 0.51042 | 5/12 | 3/4 | 7/8 | 4 false NO |
| HE | high-rate explicit | 735 | 0.55208 | 0.55208 | 10/12 | 3/4 | 5/8 | 4 false NO |

All four cells missed one aggregate query. Every high-rate cell denied all
four real-but-omitted files despite the index saying that omission means
unknown. High-rate compact copied another encoded number on seven file-line
questions; high-rate explicit did so on two. Those are the same
number-to-wrong-referent failures seen in the preflight, now on independent
source areas.

## Frozen contrasts

The family contains four tests and uses Holm step-down correction.

| Contrast | Inferential result | Raw p | Holm p | Interpretation |
|---|---|---:|---:|---|
| LE − LC, low-rate code | compact wins under every weight profile; source advantage 0.175 to 0.306 | 0.015625 | 0.046875 | A strict-output compliance effect on this corpus: all seven discordances are `YES.` versus `YES`, not evidence of changed source belief. LC still fails the omission and number-binding guards. |
| HE − HC, high-rate code | profile-sensitive; gain −0.004 to +0.179 | 0.609375 | 0.609375 | No resolved high-rate format winner. |
| HC − LC, compact rate | 5 high-only exact line answers, 0 low-only | 0.0625 | 0.125 | Positive screen, not family-wise confirmation; support gain changes sign across query profiles. |
| HE − LE, explicit rate | 10 high-only exact line answers, 0 low-only | 0.001953125 | 0.0078125 | Strong narrow evidence that explicitly supplying the target line fact improves greedy transcription. |

The exact-field score above is the preregistered primary analysis. In a
non-preregistered semantic sensitivity that accepts one terminal period on
existence answers, every cell scores 8/8 on listed existence and the low-rate
code raw p-value becomes 1. This leaves the numeric explicit-rate result
unchanged. The run did not test a formal code-by-rate interaction, so
differences between the two observed code contrasts are descriptive only.

The explicit-rate effect is not an allocation result. The twelve high-rate
facts were selected to match the twelve frozen line questions, so this arm is
a tailored channel code. A target-independent holdout, a measured operator
query distribution, a full-tree token calculation, and confirmation under
Sable's deployed sampler would all be required before wording could be
considered for production.

The four controlled points are all nondominated under the primary
token/distortion coordinates. Compact facts cost 6.5 tokens per added line
fact; explicit facts cost 10.5. The controlled HE block is 735 tokens and the
current production manifest is 710, but that comparison is descriptive only:
a controlled 20-file index and a full-tree production representation are not
the same deployment cost.

## Decision

No cell passes the absolute guards. There is no shipping candidate, no
permission to remove or bypass the trusted source resolver, and no reliability
claim. The bounded result is:

1. exact supplied facts can materially improve greedy transcription;
2. observed format differences vary descriptively with fact availability, but
   no interaction contrast was tested;
3. neither more facts nor compact syntax repairs omission honesty or referent
   binding; and
4. proof-carrying trusted reads remain the production answer.

The frozen spec, exact manifests, stable messages, source snapshot, dispatch
journal, raw rows, and machine-readable analysis are all in this directory.
