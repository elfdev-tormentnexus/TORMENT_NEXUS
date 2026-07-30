# Goal 4 grounding audit — recovered artifacts

Everything the 2026-07-30 adversarial audit produced, moved out of a
session-scoped temp directory before it was cleaned up. The findings live in
`docs/RESEARCHC_GOALS.md` under "Goal 4 addendum"; this is the evidence behind
them and the tooling to continue.

Measured against the shipped build at `cf80c630`, temperature 0.8,
`max_tokens` 180, thinking disabled, one `-np 1` slot.

## The evidence

| file | what it is |
| --- | --- |
| `journal.jsonl` | **the audit's structured output.** Every agent's returned result: findings, verbatim answers, ground truth, refutation verdicts. Read this first. |
| `system_prompt.txt` | the live prompt, dumped. The provenance map is built from it: persona text at lines 1–93, `core_memory.txt` at 119–186, the runtime block at 188–210 |
| `prompt_grounded.txt` / `prompt_ungrounded.txt` | the control pair — 17,307 b against 15,373 b. The delta is the manifest. Proof the monkeypatch took effect |
| `results.json`, `results.jsonl`, `contam_results.jsonl` | raw request/response records with per-request timings |
| `ladder_A.json`, `ladder_B.json`, `repeat_A_4.json` | the pressure ladders, including the turn-4 `MemoryLedger` repeat |
| `seq1.json`, `seq2.json`, `seq3.json` | sycophancy sequences. `seq3` was never run |
| `specA.json`, `specB.json`, `outA.json` | boundary gradient specs. `specB` holds the seven rungs that never fired |
| `transcripts/` | full agent conversations, 3.3 MB. Only needed to audit the auditors |

## The tooling

`lib_sable.py` and `ask.py` are the harness. `run2.py` takes paths on argv and
has the 600s timeout the earlier runs needed. `truth.py` and `gt.py` resolve
ground truth from the tree. `refute_misattr.py` and `refute_sycophancy.py` are
the refutation runners, `dump_prompt2.py` regenerates the prompt dumps, and
`sable-grounding-audit.js` is the five-dimension workflow — still the
specification, but see the warning below before re-running it as-is.

`smoke.py`, `timing.py`, and `timing2.py` are the calibration scripts. They are
the ones that produced the **wrong** timing model: they measured 3.6s for a
repeated question because several runs landed inside one clock tick.
`build_system_prompt` injects a live clock, so every request busts the prefix
cache. Real cost is 130–200s per question, 300s under contention.

## Before you re-run

**Fire probes serially.** Fanning five agents at one slot is what starved both
runs of their reproducibility checks — it is the single most likely mistake to
repeat, and `sable-grounding-audit.js` will make it for you by default.

The probe queue in `docs/RESEARCHC_GOALS.md` lists the unfired questions in
value order with ground truth already resolved, so a resumed run spends its
budget on the model rather than re-deriving the tree.
