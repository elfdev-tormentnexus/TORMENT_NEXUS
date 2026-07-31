# Independent audit of the frozen rate-distortion run

Audit status: **integrity and arithmetic verified, with two interpretation
qualifications.**

This was a read-only recomputation from the frozen artifacts, dispatch journal,
and raw response rows. It did not import the collector for analysis, call the
model, or use the stored correctness fields as the grading source.

## Integrity and validity checks

- The collector SHA-256 is
  `48a208932099d5d06420d488e6e4779c6c5b58e02e51d7784194b970c7dc55e7`,
  exactly the digest frozen in the spec.
- The canonical spec, stable-message, manifest, query, and selected-source
  digests all recompute to their frozen values.
- There are exactly 120 unique, contiguous tasks, dispatches, and response
  rows: 112 primary rows and eight replay sentinels. All 120 have status `ok`.
- Every task ID and execution position agrees across the frozen plan, dispatch
  journal, and response row. Every dispatch/row message digest agrees, and
  every row's spec digest, sampler, model digest, server-bundle digest, and
  live-server identity agrees with the frozen spec.
- Independent parsing and grading of the raw answers produced zero differences
  from the stored normalized answers, source-correct labels, or
  support-correct labels.
- Every before/after repository field and selected-source snapshot agrees with
  the frozen binding. There are zero source or repository drift rows.
- All eight Q01/Q25 replay answers exactly match their primary normalized
  answers. The batch therefore remains confirmatory under its frozen rules.

## Recomputed cell counts

Each entry is `source correct / support correct`.

| Cell | File line (n=12) | Aggregate (n=4) | Listed existence (n=8) | Unlisted existence (n=4) | Equal-stratum source/support |
|---|---:|---:|---:|---:|---:|
| LC | 0/0 | 3/3 | 8/8 | 0/2 | 0.4375 / 0.5625 |
| LE | 0/0 | 3/3 | 1/1 | 0/0 | 0.21875 / 0.21875 |
| HC | 5/5 | 3/3 | 7/7 | 0/0 | 0.5104167 / 0.5104167 |
| HE | 10/10 | 3/3 | 5/5 | 0/0 | 0.5520833 / 0.5520833 |

All four preregistered weight profiles and their contrast gains reproduce the
machine-readable summary. In left-minus-right orientation:

| Contrast | Equal-stratum source gain | Source-gain range | Equal-stratum support gain | Support-gain range |
|---|---:|---:|---:|---:|
| LE - LC | -0.21875 | -0.30625 to -0.175 | -0.34375 | -0.48125 to -0.225 |
| HE - HC | +0.0416667 | -0.0041667 to +0.1791667 | +0.0416667 | -0.0041667 to +0.1791667 |
| HC - LC | +0.0729167 | +0.0395833 to +0.2041667 | -0.0520833 | -0.1354167 to +0.1541667 |
| HE - LE | +0.3333333 | +0.3333333 to +0.5583333 | +0.3333333 | +0.3333333 to +0.5583333 |

## Recomputed confirmatory family

The two code comparisons use the frozen equal-stratum cluster sign-flip test.
The two rate comparisons use the frozen exact two-sided paired test over the
twelve file-line targets. Holm adjustment is over all four contrasts.

| Contrast | Inferential discordance | Raw p | Holm-adjusted p |
|---|---|---:|---:|
| LE - LC, low-rate code | seven nonzero clusters, all favouring LC | 0.015625 | 0.046875 |
| HE - HC, high-rate code | frozen 16-cluster sign-flip statistic | 0.609375 | 0.609375 |
| HC - LC, compact rate | 5 HC-only, 0 LC-only, 7 ties | 0.0625 | 0.125 |
| HE - LE, explicit rate | 10 HE-only, 0 LE-only, 2 ties | 0.001953125 | 0.0078125 |

These values exactly match `rate_distortion_summary.json`.

## Interpretation qualifications

The low-rate code result is real under the preregistered exact-field scoring
rule, but its mechanism is narrower than a grounding or belief effect. Every
one of its seven discordant answers is `YES.` under LE versus `YES` under LC.
The former is classified `NONCOMPLIANT` because the prompt required exactly
`YES`, `NO`, or `UNKNOWN`.

As a deliberately non-preregistered semantic sensitivity check, accepting one
terminal period on existence answers makes listed-existence performance 8/8
in every cell. The low-rate code statistic then has raw p = 1, and the
high-rate code statistic has raw p = 0.125. Recomputing Holm over that
sensitivity family gives:

- explicit rate: 0.0078125;
- compact rate: 0.1875;
- high-rate code: 0.25; and
- low-rate code: 1.

The frozen analysis remains the primary analysis. The sensitivity result means
the significant low-rate code contrast should be described as a strict-output
compliance effect, not evidence that compact wording changed the model's
underlying source belief. It does not alter the explicit-rate result, whose
inferential rows are the twelve numeric file-line pairs.

Finally, the experiment did not preregister or calculate a two-factor
interaction contrast. A significant low-rate code test beside a
non-significant high-rate code test does not itself establish an interaction.
The run may report that the observed format differences vary descriptively
with fact availability, but not that an interaction was confirmed.
