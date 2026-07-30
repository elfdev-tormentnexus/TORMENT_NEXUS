# Research B — final pre-cut audit handoff

Written 2026-07-30 for Claude's final review before any Research B capsule cut
or GitHub release work. This is a **read-first, audit-only** handoff: identify
real defects and missing release work; do not cut, upload, publish, or make
unrequested changes while reviewing.

## Audit base checkpoint

- The final audit began from `master` synchronized with `origin/master` at
  **`a10d40b Hand off the researchB pre-cut audit`**.
- The repaired checkpoint is the commit containing this document.
- A fresh complete regression run at that repaired checkpoint passed with
  **no failures and 2 expected skips** (1,071 tests at the time; do not turn
  that count into a future release promise).
- All six council GGUFs and the one explicitly quarantined partial matched
  `models/embedding/INTERLINGUA_MODEL_REGISTRY.json` exactly by SHA-256.

## What landed after the earlier release audit

1. **Research B identity is real end-to-end.**
   `tools/package_release.py` and `tools/package_model_pack.py` now use
   `RELEASE_VERSION = "researchB"`; generated package text, README, Windows
   installation guide, checklist, and release-facing documents follow it.
   `SABLERESEARCHA_MANIFEST1` intentionally remains untouched: it is the
   published combined-manifest wire-format discriminator, not a release name.

2. **The original audit's release gaps are closed in source.**
   `.gitattributes` pins text endings; the release whitelist includes the
   Sable preservation field, Super Dev icon and icon builder; the embedded
   model council registry is tracked; the suite no longer leaves a real
   llama-server behind; and machinespirit checks authenticated live servers
   rather than mistaking configuration for availability.

3. **Evidence and trust work is present.**
   Reasoning receipts distinguish prompt evidence from inferred model output,
   and the library classifies imported material at ingestion. The retrieval
   excerpt cap and receipts agree: a dropped excerpt cannot be cited.

4. **Front door and visual work are present.**
   `TORMENT_NEXUS.bat` dispatches to the four existing modes without
   duplicating their configuration. The panel has direct machinespirit and
   machinesoul readouts; the Sable field gained measured display-range,
   lattice, and audio-reactivity work.

5. **New generated fetcher.**
   `tools/build_researchb_fetcher.py` is a new, stdlib-only *post-cut*
   generator. Given the final release directory, it discovers the actual
   required Windows capsules, bootstrap, manifest and reassembler; embeds
   their current SHA-256s; and atomically writes `FETCH_SABLERESEARCHB.bat`.
   The batch helper uses `curl.exe -C -` and `certutil`, skips files already
   verified, and does not include optional 14B capsules by default. An
   explicitly named `--include-optional-14b` variant exists only when asked.
   Six dedicated tests cover ordinary discovery, optional inclusion, gapped
   or malformed parts, missing bootstrap/tag refusal, output confinement, and
   a live Windows resume inside a path containing `!`.

6. **Generated one-click decompiler.**
   `tools/build_researchb_decompiler.py` builds the plaintext bootstrap from
   the exact combined cut manifest. It does not remember part counts or
   decoded segment names. It accepts all or none of the optional 14B fields,
   confines that component below `models/`, recovers the manifest and
   reassembler through machinesoul, verifies both reconstructed components,
   and only then invokes `setup.bat`.

7. **Public materials are updated for this checkpoint.**
   README, INSTALL_WINDOWS, ARCHITECTURE, RELEASE_CHECKLIST and CHANGELOG
   describe the fetcher, current Super Dev passcode/session rules, the front
   door, evidence receipts, trust classification, live server probing and
   prompt shedding. The beginner-document regression now names the fetcher in
   both places and keeps their release asset lists identical.

## Current transient workspace state

- C: currently has roughly **83 GiB free**, enough for the planned
  clean-room release work. Old Research A release assets and an obsolete Beta
  6 smoke install were moved out of their live paths. No active Research B
  model, music, cache, or council artifact was removed.
- `dist/TORMENT_NEXUS` currently exists and is about **12.09 GiB**, but it is
  **incomplete**: a staging command was deliberately terminated when the
  operator requested this audit, before it wrote `RELEASE_MANIFEST.json` or
  completed `--verify-only`. Treat it as disposable partial output. Do not
  cut it, verify it as a final stage, or infer anything from it. Rebuild from
  the clean audited commit after the audit/fixes are complete.
- No Research B capsule, combined manifest capsule, reassembler capsule,
  generated one-click decompiler asset, generated fetcher asset, tag, release
  draft, or GitHub upload exists yet. Their generators are present and tested;
  the final files cannot truthfully exist before the reviewed cut.

## Remaining gates — none may be silently assumed complete

The source is in good condition; that is not the same as release readiness.
The current staged record is `docs/RESEARCHB_STAGING_PLAN.md`.

- Stage 0: suite/calibration baseline recorded. The latest full suite was
  rerun at `38d1104`; live calibration evidence was recorded earlier that
  day.
- Stage 1: automated coverage exists, but its human launcher/sensor/Super Dev
  checks are not all recorded. Do **not** activate an autonomous writing
  session merely to tick a release box; it requires the operator's local
  passcode and explicit supervision.
- Stage 2: panel check 2.1 was observed; checks 2.2–2.6 remain manual.
- Stage 3: 3.1 and 3.5 are now additionally evidenced by exact local hashes.
  Loading all six observers, proving ordinary retrieval remains unchanged,
  and measuring two-server RAM remain open.
- Stage 4: repeatable live benchmarks remain open.
- Stage 5: no valid Research B stage/cut/reassembly/install/tag/upload has
  happened. The incomplete `dist/TORMENT_NEXUS` above is not Stage 5.

The non-negotiable release proof remains:

1. build and verify a clean stage from the final clean commit;
2. create, review, and bind the APNG cut plan hash;
3. cut all required and optional capsule sets;
4. decompile every capsule into a clean directory;
5. reassemble the exact tree and perform the actual install/first-launch
   check; then
6. generate the fetcher from those final asset bytes, draft-upload, download
   every remote asset, and compare/reassemble the downloaded copies before
   publishing.

## Audit emphasis for this final pass

Please prioritize release-affecting correctness over broad stylistic change:

- fetcher safety and asset-set truthfulness;
- compatibility of the new fetcher with the planned decompiler/reassembler
  output names;
- release whitelist and public-document completeness;
- whether the updated README/INSTALL behavior matches the actual programs;
- `TORMENT_NEXUS.bat` dispatch/leftover-server behavior and Super Dev wording;
- evidence receipt/trust labels staying honest at the prompt boundary;
- any source/package check that can prove the final stage would omit or
  mislabel a file.

Record defects with evidence. Keep historical Research A records historical;
do not rename `SABLERESEARCHA_MANIFEST1`, the Research A patch tools, or
Research A research records. Avoid opportunistic feature work. If a genuine
fix is needed, make it narrowly, test it, and leave a clear final source
commit for a fresh build.

## Final audit continuation — completed 2026-07-30

Claude's cutoff still produced one reproducible finding: the original fetcher
hashed and deleted an existing partial target before calling `curl -C -`, so
its cross-invocation resume claim was false. The continuation reproduced that
flow and closed it without weakening verification:

- downloads now use `asset.partial` across invocations;
- an incomplete partial is resumed;
- a complete-size but wrong partial is discarded and restarted;
- the published asset name appears only after SHA-256 succeeds;
- an interrupted transfer keeps only the visibly temporary name; and
- delayed expansion is disabled, so a valid Windows folder containing `!`
  is not corrupted by the batch interpreter.

The same review found that the checklist required a generated one-click
decompiler but no generator existed. That was a reproducibility gap at the
most important install boundary. The manifest-driven generator above closes
it. A live miniature release test now performs the whole chain with actual
capsules: cut both components, encode the combined manifest and reassembler,
run the generated launcher on Windows from a `!` path, reconstruct and verify
the Windows tree, install the optional model, run setup, and remove temporary
segments. This test also caught that the recovered reassembler needs
`machinesoul.py` beside it; the launcher now supplies that dependency.

Other corrections made in the same narrow pass:

- the release checklist now uses one unambiguous final directory,
  `SABLERESEARCHB\release`, for both capsule sets and every bootstrap asset;
- the optional component must preserve its final `models/` path;
- the checklist names the combine, wrap, decompiler generation, and fetcher
  generation order explicitly;
- the stale Research A calibration-patch paragraph was removed from the
  Research B Windows guide; and
- troubleshooting no longer refers to the retired support/research-capsule
  architecture.

Verification at the repaired checkpoint:

- generated fetcher executed successfully with a resumable partial, a damaged
  final target, a complete-size bad partial, and a destination containing `!`;
- generated decompiler executed end to end against real tiny machinesoul
  capsules, including the optional component and setup;
- every mandatory package-whitelist path exists; and
- full suite: **1,071 passed, 2 expected skips, no failures**.

This completes the source and release-tooling audit. It does **not** convert
the still-empty manual rows in `docs/RESEARCHB_STAGING_PLAN.md` into passes,
approve a cut map that does not exist yet, or validate the incomplete
`dist/TORMENT_NEXUS` directory. Rebuild that stage from this final clean commit
before any plan or cut.
