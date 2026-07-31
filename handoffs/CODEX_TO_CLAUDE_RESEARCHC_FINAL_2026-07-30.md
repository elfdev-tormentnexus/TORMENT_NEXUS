# Codex → Claude: finish Research C testing and release preparation

Date: 2026-07-30 (America/Toronto)

## Operator intent

Finish every defensible Research C implementation and bounded test from this
session, reconcile the results without overclaiming, and prepare a Research C
release. Do not defer useful work merely to create a Research D bucket.

The operator reports that the visible Sable session is in **hazard mode** and
is being used only for offline music. Treat the mode as operator-reported, not
independently proven. The remaining probes bypass the UI and call the same
one-slot director directly. Do not alter Sable's session, settings, memories,
music state, or active binaries.

## Exact stop point

No coherence/order live call has run. The new 98-call collector has **NO-GO**
status from an independent offline audit until the two blockers below are
fixed and re-audited.

The last known live topology was:

- assistant Python PID `254736`;
- one-slot director PID `53408`, loopback port `8080`, context `8192`,
  `-np 1`;
- pooled embedder PID `137692`, port `8082`;
- unpooled machinespirit helper PID `173648`, port `8084`;
- no listener on `8099`.

These are observations, not durable identities. Re-query them before any live
run. The operator may close or restart Sable after this handoff.

Repository HEAD is still:

```text
e9e05e1 Prepare Research C measurement and recovery release
```

The worktree is intentionally dirty with Codex/Claude/user Research C work.
Do not reset, restore, clean, or overwrite it.

## Work completed and verified

### Grounding audit corrections

The old `voice_confirmatory` conclusion was backwards. Regrading all frozen
raw replies gives:

- grounded unsupported concrete voice mechanism: `1/8`;
- ungrounded: `8/8`;
- ungrounded-only discordances: `7`;
- grounded-only: `0`;
- exact two-sided paired McNemar `p = 0.015625`.

The corrected grading is preserved in
`handoffs/researchc_evidence_2026-07-30/voice_confirmatory_grading.json`.

Other frozen results remain:

- `ui.py` line-count prompt: grounded copied the directory aggregate `8/8`;
  ungrounded refused `8/8`; paired `p = 0.0078125`;
- real but unnamed `machinespirit_shadow.py`: grounded false denial `7/7`,
  ungrounded refusal `7/7`;
- nonexistent `MemoryLedger` and false authorship: accepted `6/6` in both
  conditions, so those are base-model agreement biases rather than a measured
  manifest effect.

### Compression/AIT correction

Equal-length gzip is not a truth detector:

- voice criterion-contrasting pairs: `7/7` in the proposed direction,
  mean difference `-7.43` bytes, exact `p = 0.015625`;
- boundary family: `5/14` in that direction, one tie, mean `+1.73`,
  exact `p = 0.424`;
- pooled non-tied: `12/21`, mean `-1.18`, exact `p = 0.6636`.

The effect follows assertive-versus-hedged register and does not generalize.

### Production changes already present in the worktree

- `assistant/core/research_c.py`
  - privacy-safe top-candidate telemetry;
  - allowlisted workflow/stage identifiers;
  - unknown metadata keys replaced with digest aliases;
  - artifact/prompt digests must be actual 64-hex SHA-256 values;
  - server provenance now hashes the full CPU runtime component family,
    including `mtmd.dll`, without a stale size/mtime cache.
- `assistant/main.py`
  - the live clock is the final runtime-context field, increasing reusable
    prompt-prefix length without claiming a universal latency multiplier.
- `assistant/memory/core_memory.txt`
  - stale `researchA` release labels changed to `researchC`.
- `tools/researchc_report.py`
  - strict Wilson/SPRT count validation;
  - exact sign/McNemar, Holm correction, empirical rate–distortion,
    probability-form QQ and marginal-selectivity residuals, response-coherence
    violations, binary bit-price, two Fisher parameterizations, and rank AUC.
- `tools/researchc_probe.py`
  - six-call aggregate-substitution preflight;
  - resume now revalidates spec, prompt, live model/server bindings, every
    existing row, parsing/classification, truth, sampler, and repository state;
  - remains source-checkout-only because it persists a full production prompt.
- `tools/package_release.py`
  - no longer recursively packages 88 llama.cpp programs;
  - packages the proven eight-file CPU server dependency closure;
  - accepts `--llama-runtime-dir` or
    `TORMENT_NEXUS_RELEASE_LLAMA_RUNTIME_DIR`;
  - rejects staged PE files containing the current checkout/profile path;
  - includes `docs/RESEARCHC_THEORY_LEDGER.md`;
  - deliberately does **not** package `tools/researchc_probe.py`.

The eight-file server closure, verified recursively with PE imports, is:

```text
llama-server.exe
llama-server-impl.dll
llama-common.dll
mtmd.dll
llama.dll
ggml.dll
ggml-base.dll
ggml-cpu.dll
```

Relevant tests and release docs were updated. The most recent checks were:

- focused Research C/privacy/package tests: `66 passed`;
- full suite before the packaging-hardening patch: `1,150 passed`,
  `2` expected platform skips, `0` failures;
- packaging/release tests after the patch: `36 passed`;
- `git diff --check`: clean.

Run the full suite again after all remaining edits; the `1,150` result is not
the final release result.

### Six-call causal preflight

The aggregate substitution changed only:

```text
assistant/ui 3f 4,353L
assistant/ui 3f 7,731L
```

Observed:

- aggregate control copied `4,353 → 7,731`;
- `ui.py` copied `4,353 → 7,731`;
- `vector_panel.py` did not follow the manipulation cleanly and copied an
  unrelated visible aggregate.

Verdict: causally positive but inconclusive; six calls are not a powered test.
The original generated summary had a parsing-rule bug and is preserved beside
the corrected reanalysis.

### Completed 120-call controlled-index/rate experiment

Evidence is under
`handoffs/researchc_experiments_2026-07-30/rate_distortion/`.

Validity:

- `120/120` completed: `112` primary + `8` exact replays;
- zero HTTP failures, retries, repository/source drift, or replay-answer
  mismatches;
- independent recomputation verified tasks, hashes, raw regrading, cells,
  profiles, exact tests, and Holm adjustment.

Primary cells:

| Cell | Tokens | Equal-stratum source/support | File lines | Aggregate | Listed | Unlisted |
|---|---:|---:|---:|---:|---:|---|
| LC low compact | 614 | .4375 / .5625 | 0/12 | 3/4 | 8/8 | 2 UNKNOWN, 2 false NO |
| LE low explicit | 609 | .21875 / .21875 | 0/12 | 3/4 | 1/8 | 4 false NO |
| HC high compact | 692 | .51042 / .51042 | 5/12 | 3/4 | 7/8 | 4 false NO |
| HE high explicit | 735 | .55208 / .55208 | 10/12 | 3/4 | 5/8 | 4 false NO |

Confirmatory family:

- low code `LE−LC`: raw `.015625`, Holm `.046875`;
- high code `HE−HC`: raw/Holm `.609375`;
- compact rate `HC−LC`: raw `.0625`, Holm `.125`;
- explicit rate `HE−LE`: raw `.001953125`, Holm `.0078125`.

Interpretation corrections from the independent audit:

- every low-code discordance was `YES.` under LE versus strict `YES` under LC;
  accepting one terminal period makes the low-code raw `p = 1`;
- therefore that result is output-format compliance, not changed source
  belief;
- no code-by-rate interaction contrast was preregistered or tested;
  significant-versus-nonsignificant is not an interaction;
- the explicit-rate result is real but narrow: target-matched supplied line
  facts improved greedy transcription;
- all four cells fail omission-honesty/referent-binding guards, so none is a
  shipping or screening candidate;
- the trusted proof-carrying source resolver remains the product answer.

One provenance caveat must be added wherever this run is described: its frozen
collector-era `server_bundle_sha256`
`2cfd58b8b4a2e9a1081cab1168877dfa6598f0c430c6970afbd41a37f08f96ab`
omitted `mtmd.dll`. The launcher, main implementation libraries, model,
repository, prompt, and sampler were still bound, but do not call that old
value a complete dependency-closure digest.

## The 98-call coherence/order/bit-price collector

Files:

- `handoffs/researchc_open_threads_tools/coherence_probe.py`;
- `handoffs/researchc_open_threads_tools/test_coherence_probe.py`.

Offline collector/rate tests passed `23/23` before the independent audit.
The protocol uses eight independent source files, two exact paraphrases, six
binary-probability calls per file/paraphrase, and two replay sentinels:

```text
8 targets × 2 wordings × 6 measurements + 2 replays = 98
```

It constructs complete AB and BA response distributions from:

```text
q(A)
q(B | forced A=Yes)
q(B | forced A=No)
q(B)
q(A | forced B=Yes)
q(A | forced B=No)
```

The actual messages use a public controlled source-inventory prompt. They do
not call or persist `build_system_prompt`, persona, chosen name, memory,
conversation recall, ambient state, room state, clock, edit prose, credentials,
or absolute paths. Hazard mode is recorded as operator-reported only.

### Independent audit: NO-GO blockers

Fix these before any live call:

1. `_public_source_context()` currently consumes
   `source_awareness.inventory()`, which includes untracked `.py`/`.md` files.
   That can freeze private filenames/counts and lets unrelated untracked work
   move aggregates. Filter the public inventory through a Git-tracked
   allowlist (best after publication-safe implementation files are committed),
   or use an explicit frozen public inventory. Add a regression test with an
   untracked sentinel and prove it is absent from paths, totals, directory
   aggregates, and recency.
2. The complete sanitized runtime/topology binding is checked before launch,
   but each dispatch currently rechecks only the raw director identity.
   Recheck the full sanitized binding before every dispatch and after the final
   response so a newly opened `8099`, changed helper, changed assistant parent,
   or topology change invalidates the batch.

Minor hardening requested by the auditor:

- validate `top_probs` candidate token IDs against the frozen one-token
  `Yes`/`No` IDs, not only their rendered strings.

Everything else received GO: exact schedule, probability math, parser shape,
dispatch-first/no-retry semantics, safe/raw identity separation,
operator-reported hazard wording, and analyze-only isolation.

After fixes:

```powershell
python -m unittest `
  handoffs.researchc_open_threads_tools.test_coherence_probe `
  handoffs.researchc_open_threads_tools.test_rate_distortion_probe

python handoffs\researchc_open_threads_tools\coherence_probe.py --dry-run
```

`--dry-run` contacts only read-only runtime/tokenization endpoints; it must not
freeze rows. Inspect its output for zero local paths/secrets. Get another
independent GO, then run serially:

```powershell
python handoffs\researchc_open_threads_tools\coherence_probe.py
```

Do not edit or commit anything while collection is in flight. The helper sends
an inert console key pulse to stop Sable's idle timer from racing the one
director slot. Do not parallelize requests. If a dispatch intent is written
and the call fails, do not retry that trial as confirmatory evidence.

Afterward run `--analyze-only`, independently recompute from raw probabilities,
and add a concise evidence README. Interpret:

- positive `q(B)-q(A)` only as a response-coherence defect;
- AB/BA marginal differences only as context/order effects;
- each constructed joint obeys total probability by construction;
- QQ is a descriptive compatibility residual;
- balanced bit-price is the same log-odds contrast, not independent evidence;
- no result proves quantum behavior, contextuality, a sheaf obstruction, or a
  calibrated shared belief state.

## Evidence-publication privacy work still required

An audit found no copied API key, agent token, private conversation-history
text, durable-memory text, or activity-log text in the new experiment files.
Nevertheless, these raw artifacts must **not** be committed:

```text
handoffs/researchc_experiments_2026-07-30/preflight_prompts.json
handoffs/researchc_experiments_2026-07-30/rate_distortion/rate_distortion_stable_messages.json
handoffs/researchc_experiments_2026-07-30/rate_distortion/rate_distortion_spec.json
handoffs/researchc_experiments_2026-07-30/rate_distortion/rate_distortion_rows.jsonl
```

The prompt artifacts contain the exact runtime system prompt, including
installation-local chosen-name state. The raw rate spec/rows contain absolute
host paths. Add explicit `.gitignore` entries before staging.

Create a clearly labelled public derivative:

- retain every response, grading, statistical, task, and timing field;
- consolidate one sanitized binding record containing only basenames,
  roles/PIDs, loopback ports, sizes, revision, and cryptographic hashes;
- remove/sanitize at least:
  - assistant executable path;
  - machinespirit-helper executable path;
  - listener executable path;
  - model path;
  - model alias if it contains a path;
  - credential/query-bearing server URL (retain loopback host/port only);
- preserve SHA-256 commitments to each private original;
- compute hashes for each public artifact;
- label the transformation version and every removed field path;
- do not claim the transformed bundle revalidates under the original
  collector digest;
- correct the old `assistant_mode.independently_verified=true` wording to say
  hazard was operator-reported and only process topology was checked;
- record the incomplete pre-mtmd server-bundle caveat above.

Safe unchanged candidates include the experiment READMEs, preflight
reanalysis/rows/spec/summary, rate dispatch/manifests/queries/source snapshot/
summary, and `INDEPENDENT_AUDIT.md`. Still scan every staged file rather than
trusting this list.

The attempted publication subtask was interrupted for this handoff before it
wrote files. Verify that `.gitignore` has no new evidence rules before assuming
this was done.

Two recovered tools were made portable:

- `handoffs/researchc_open_threads_tools/qq_probe.py`;
- `handoffs/researchc_open_threads_tools/compression_reanalysis.py`.

They no longer hardcode this Windows username/checkout; `py_compile` passed.
The old simultaneous QQ batch remains a narrow null, not release-bound
contextuality evidence.

## Release-package blocker and completed hardening

The active `llama.cpp/build/bin/Release` is **not publishable**. Forty current
PE files embed the maintainer checkout/profile path. Do not copy, replace, or
rebuild the active directory while Sable uses it.

Build a separate path-neutral Release directory from the same llama.cpp
revision and CPU configuration:

- `BUILD_SHARED_LIBS=ON`;
- `GGML_BACKEND_DL=OFF`;
- CPU `ON`;
- CUDA, Vulkan, HIP, SYCL, RPC, and BLAS `OFF`;
- MSVC `/pathmap` covering the checkout/profile source prefix.

Verify the exact eight files exist and contain neither checkout nor profile
strings (ASCII or UTF-16). Prefer a neutral build directory outside the user
profile. Review the resulting PE dependency closure again.

Only after the final publication-safe source commit:

```powershell
python tools\package_release.py --skip-download `
  --llama-runtime-dir C:\path\to\path-neutral\Release
python tools\package_release.py --verify-only
```

Then run the regression suite and a startup/privacy smoke test from a
disposable copy of the staged package. Rebuild the final stage from the exact
clean commit and verify it again. Do not cut machinesoul capsules, tag, upload,
or publish without the operator approving the exact final plan/hash.

## Documentation reconciliation still required

After the coherence run and independent audit, update:

- `docs/RESEARCHC_GOALS.md`;
- `docs/RESEARCHC_THEORY_LEDGER.md`;
- `docs/RELEASE_NOTES_researchC.md`;
- `handoffs/2026-07-30_researchc_open_threads.md`;
- the expanded-experiment README(s).

Required language:

- rate experiment measured, not “in progress”;
- low-code result is punctuation compliance;
- explicit high-rate line-fact effect is narrow and not an allocation result;
- no encoding passed absolute guards;
- coherence/order/bit-price results are descriptive and non-authoritative;
- gzip is register-correlated, not a detector;
- density-matrix memory migration is rejected as stated because pure-state
  trace overlap squares cosine and loses sign;
- dequantized length-squared retrieval has no value at the current scale;
- EVT/Rasch/Weitzman/CUSUM/Doob proposals lack their prerequisites;
- proof-carrying trusted source answers, bounded top-candidate telemetry,
  complete server provenance, clock reorder, and endpoint-recovery simulations
  are the shipped work;
- the real four-case Windows display/audio hardware matrix remains manual and
  must not be called hardware-validated until actually performed.

## Recommended continuation order

1. Inspect `git status` and this handoff. Preserve all existing changes.
2. Add evidence-private `.gitignore` rules and finish the sanitized public
   evidence derivative.
3. Fix the two coherence NO-GO blockers plus token-ID validation; run offline
   tests and get an independent GO.
4. Run all focused and full offline tests. Commit the publication-safe
   implementation/tool/test state so the collector's Git-tracked public
   inventory is stable. Do not include raw private evidence.
5. Recheck the live one-slot runtime; run dry-run, then the 98 serial calls
   with no filesystem edits during collection.
6. Independently recompute the coherence result and write its evidence README.
7. Reconcile all Research C docs and run the full suite again.
8. Build and verify the separate path-neutral eight-file llama runtime.
9. Commit the final docs/evidence, build the package from that exact clean
   commit, verify package/tests/privacy twice, and stop before cut/publish for
   operator approval.

The cardinal rule remains the one that made this session useful: a null,
refutation, privacy correction, or blocked release claim is a result. Do not
turn it into a positive finding to make Research C look finished.
