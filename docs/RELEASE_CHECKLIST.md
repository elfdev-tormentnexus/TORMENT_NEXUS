# TORMENT_NEXUS researchC release checklist

This is a maintainer document, not an installation guide. Windows users should
follow [Installing on Windows](INSTALL_WINDOWS.md).

researchC has one public preservation boundary: machinesoul PNG/APNG
capsules. The verified staged directory is cut directly. It is never flattened
through ZIP, tar, or another public encoder first, because that would erase the
file and code seams used by the cut logic.

1. Run the complete regression suite:

   ```powershell
   .\setup\test_assistant.bat
   ```

   Run the focused singing gates and preserve their count:

   ```powershell
   Push-Location assistant
   python -m unittest tests.test_freestyle_song tests.test_singing_easter_egg
   Pop-Location
   ```

   Before calling the songs validated, listen to uncached Daisy Bell, Come
   Josephine, and one generated song on the target Windows account. Record
   intelligibility, chord alignment, output level, Escape cancellation, and
   cache reuse. This is human evidence and cannot be replaced by the score
   invariants.

   Run the fixed offline-library probe separately and retain its JSON report:

   ```powershell
   python -B tools\researchc_library_probe.py `
     --output assistant\logs\researchc_library_probe.json
   ```

   Confirm the built-in fixture indexes exactly 18 integrity-matched sources
   and 39 chunks, achieves 18/18 candidate/top-1/top-3 recall and 10/10
   known-unknown abstention, and preserves citation/source-digest pairing.
   Preserve the declared specialist-bait negative result rather than changing
   the cases: 18/18 positive recall, 5/10 known-unknown abstention, and 2/18
   specialist intrusions.

   The first live librarian experiment is evidence, not a release dependency:
   the tested Qwen3 4B Instruct GGUF does not ship and failed promotion. Confirm
   that every release-facing document keeps the observer off, shadow-only, and
   unable to affect retrieval. Verify the sanitized result records 11/16
   strictly valid decisions, 9/16 correct valid decisions, and 1/8
   forward/reversed-order agreement, with model, server, cases, and experiment
   digests bound to the run. Verify the separately sanitized preregistered
   shipped-director result records 15/16 validity, the same 9/16 correctness,
   5/8 order agreement, and a failed promotion gate.

2. Build the intended clean commit into the staged directory and verify it.
   Supply a separately reviewed llama.cpp `Release` directory compiled with
   checkout paths mapped out (for MSVC, use `/pathmap`). The directory must
   contain exactly the runtime closure used by the CPU server:
   `llama-server.exe`, `llama-server-impl.dll`, `llama-common.dll`, `mtmd.dll`,
   `llama.dll`, `ggml.dll`, `ggml-base.dll`, and `ggml-cpu.dll`.

   ```powershell
   python tools\package_release.py --skip-download `
     --llama-runtime-dir C:\path\to\path-neutral\Release
   python tools\package_release.py --verify-only
   ```

   The override is release-build-only; the staged destination and Sable's
   normal runtime configuration do not change. The builder copies no benchmark,
   conversion, quantization, or test executables from the CMake output tree.
   Verification refuses any staged `.exe`, `.dll`, or `.pyd`, and any staged
   source/document/config text, that still embeds this checkout root or the
   maintainer's user-profile path.

   Inspect the staged tree, not only the checkout: confirm
   `assistant\knowledge\builtin_manifest.json` contains exactly the 18 staged
   cards and each digest matches, the fixed probe inputs and wrapper are
   present, and any librarian evidence cited by staged documentation is itself
   present and path-clean. The librarian probe helper must resolve the staged
   bundled Python and staged llama-server runtime; an operator-supplied model
   must remain an explicit, separately reviewed input.

3. Prepare—but do not execute—the vector-aware cut:

   ```powershell
   python tools\machinesoul_release.py plan `
     dist\TORMENT_NEXUS `
     --prefix SABLERESEARCHC-WINDOWS `
     --out SABLERESEARCHC\CUT_PLAN_WINDOWS.json `
     --markdown SABLERESEARCHC\CUT_PLAN_WINDOWS.md

   python tools\machinesoul_release.py render `
     SABLERESEARCHC\CUT_PLAN_WINDOWS.json `
     --out SABLERESEARCHC\CUT_PLAN_WINDOWS.png
   ```

   The lossless APNG is the review surface. Frame 0 shows the whole release;
   later frames show one proposed capsule each. Green marks whole-file/release
   seams, cyan marks a text rule/`def` seam, magenta marks a quiet aligned
   in-file vector window, and orange marks a forced fallback. Coloured bands
   are source files; the lower graph is local vector activity.

4. Review the APNG, Markdown table, and exact plan SHA-256 with the operator.
   Do not cut until the operator approves that specific hash.

5. Supply the approved plan digest back to the cutter:

   ```powershell
   python tools\machinesoul_release.py cut `
     SABLERESEARCHC\CUT_PLAN_WINDOWS.json `
     --approved-sha256 <REVIEWED_PLAN_SHA256> `
     --out-dir SABLERESEARCHC\release `
     --manifest SABLERESEARCHC\MANIFEST_WINDOWS.json
   ```

   The cutter refuses a changed plan. Every capsule is decompiled immediately
   after it is written and compared with the direct staged source before the
   temporary segment is removed.

6. Repeat the plan, APNG review, approval, and cut for the optional 14B
   companion, using prefix `SABLERESEARCHC-14B` and a staging root that places
   the exact reviewed GGUF recorded in [Models](../MODELS.md) at its final
   `models/` path. Write those capsules into the same
   `SABLERESEARCHC\release` directory and the component record to
   `SABLERESEARCHC\MANIFEST_14B.json`. It remains optional for recipients but
   follows the identical preservation boundary.

7. Combine the two component manifests, then wrap the two reconstruction
   support files with machinesoul:

   - `SABLERESEARCHC\MANIFEST_COMBINED.json`, produced by
     `machinesoul_release.py combine`, as
     `SABLERESEARCHC-MANIFEST.png`;
   - `tools/machinesoul_release.py` as
     `SABLERESEARCHC-REASSEMBLER.png`.

   Write both capsules into `SABLERESEARCHC\release`, and copy the current
   `tools/machinesoul.py` there byte-for-byte. Do not upload either support
   source file raw; `machinesoul.py` is the unavoidable plaintext inverse.

8. Generate `DECOMPILE_SABLE_researchC.bat` from that exact combined manifest
   with `tools/build_researchc_decompiler.py`, then generate
   `FETCH_SABLERESEARCHC.bat` from the completed `SABLERESEARCHC\release`
   directory with `tools/build_researchc_fetcher.py`. Test both generated
   files. The fetcher is plaintext by necessity:
   it is the small, resumable first download that obtains the decompiler and
   the capsules. It must be generated from the actual part names and digests,
   never maintained as a remembered list. The one-step launcher must:

   - decompile the manifest and reassembler capsules;
   - decompile every exact `SABLERESEARCHC-WINDOWS.partNN.png`;
   - invoke the recovered reassembler;
   - verify every final file;
   - reconstruct the install directory directly and run `setup.bat`;
   - install the 14B companion when all optional capsules are present;
   - skip the 14B set when none are present; and
   - refuse a partial optional set.

   The normal fetcher downloads only the required Windows set. The optional
   14B companion is offered as the clearly named
   `FETCH_SABLERESEARCHC_WITH_14B.bat`, generated and separately tested
   beside it, so both paths run one click from download to a working
   installation.

9. Create GitHub tag/title `researchC` as a draft and upload only:

   - every `SABLERESEARCHC-WINDOWS.partNN.png`;
   - every optional `SABLERESEARCHC-14B.partNN.png`;
   - `SABLERESEARCHC-MANIFEST.png`;
   - `SABLERESEARCHC-REASSEMBLER.png`;
   - `FETCH_SABLERESEARCHC.bat`;
   - `FETCH_SABLERESEARCHC_WITH_14B.bat`;
   - `machinesoul.py`;
   - `DECOMPILE_SABLE_researchC.bat`.

10. Compare every GitHub asset's size and SHA-256 with its retained local
    copy. Download every remote capsule again, decompile it, reassemble the
    full remote tree and optional 14B model, and compare every reconstructed
    file digest with the local manifest.

11. Inspect the draft release in the browser. Preserve the model, rights,
    privacy, safety, Rosetta Stone, machinesoul/machinespirit, research-loss,
    and known-gap disclosures. Publish only after the operator explicitly
    approves the verified draft.

On a constrained drive, remove only reproducible intermediates after their
hashes and remote copies are verified. Never test `setup.bat` inside the final
staged source and then ship that mutated folder; rebuild and verify a clean
stage first.
