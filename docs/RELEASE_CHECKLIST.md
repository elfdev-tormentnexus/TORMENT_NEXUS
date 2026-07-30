# TORMENT_NEXUS researchB release checklist

This is a maintainer document, not an installation guide. Windows users should
follow [Installing on Windows](INSTALL_WINDOWS.md).

researchB has one public preservation boundary: machinesoul PNG/APNG
capsules. The verified staged directory is cut directly. It is never flattened
through ZIP, tar, or another public encoder first, because that would erase the
file and code seams used by the cut logic.

1. Run the complete regression suite:

   ```powershell
   .\setup\test_assistant.bat
   ```

2. Build the intended clean commit into the staged directory and verify it:

   ```powershell
   python tools\package_release.py --skip-download
   python tools\package_release.py --verify-only
   ```

3. Prepare—but do not execute—the vector-aware cut:

   ```powershell
   python tools\machinesoul_release.py plan `
     dist\TORMENT_NEXUS `
     --prefix SABLERESEARCHB-WINDOWS `
     --out SABLERESEARCHB\CUT_PLAN_WINDOWS.json `
     --markdown SABLERESEARCHB\CUT_PLAN_WINDOWS.md

   python tools\machinesoul_release.py render `
     SABLERESEARCHB\CUT_PLAN_WINDOWS.json `
     --out SABLERESEARCHB\CUT_PLAN_WINDOWS.png
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
     SABLERESEARCHB\CUT_PLAN_WINDOWS.json `
     --approved-sha256 <REVIEWED_PLAN_SHA256> `
     --out-dir SABLERESEARCHB\package `
     --manifest SABLERESEARCHB\MANIFEST_WINDOWS.json
   ```

   The cutter refuses a changed plan. Every capsule is decompiled immediately
   after it is written and compared with the direct staged source before the
   temporary segment is removed.

6. Repeat the plan, APNG review, approval, and cut for the optional 14B
   companion, using prefix `SABLERESEARCHB-14B` and the exact reviewed GGUF
   recorded in [Models](../MODELS.md). It remains optional for recipients but
   follows the identical preservation boundary.

7. Wrap the two reconstruction support files with machinesoul:

   - the final release manifest as `SABLERESEARCHB-MANIFEST.png`;
   - `tools/machinesoul_release.py` as
     `SABLERESEARCHB-REASSEMBLER.png`.

   Do not upload either source file raw.

8. Generate and test `DECOMPILE_SABLE_researchB.bat`. The only unavoidable
   plaintext bootstrap downloads are that one-click launcher and
   `machinesoul.py`. The launcher must:

   - decompile the manifest and reassembler capsules;
   - decompile every exact `SABLERESEARCHB-WINDOWS.partNN.png`;
   - invoke the recovered reassembler;
   - verify every final file;
   - reconstruct the install directory directly and run `setup.bat`;
   - install the 14B companion when all optional capsules are present;
   - skip the 14B set when none are present; and
   - refuse a partial optional set.

9. Create GitHub tag/title `researchB` as a draft and upload only:

   - every `SABLERESEARCHB-WINDOWS.partNN.png`;
   - every optional `SABLERESEARCHB-14B.partNN.png`;
   - `SABLERESEARCHB-MANIFEST.png`;
   - `SABLERESEARCHB-REASSEMBLER.png`;
   - `machinesoul.py`;
   - `DECOMPILE_SABLE_researchB.bat`.

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
