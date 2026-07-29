# TORMENT_NEXUS researchA release checklist

This is a maintainer document, not an installation guide. Windows users should
follow [Installing on Windows](INSTALL_WINDOWS.md).

The release is built from a clean source tree. The package denylist keeps
personal runtime state out, and machinesoul carries the split package parts
without changing their bytes.

1. Run the source regression suite:

   ```powershell
   .\setup\test_assistant.bat
   ```

2. Build and verify the archive from the intended clean commit:

   ```powershell
   python tools\package_release.py --archive --skip-download
   python tools\package_release.py --verify-only
   ```

3. Split it below GitHub's asset ceiling and prove the numbered parts rejoin:

   ```powershell
   python tools\package_release.py --split --discard-stage
   ```

   This creates the exact versioned archive, raw numbered parts, and generated
   reassembler:

   ```text
   dist\TORMENT_NEXUS-researchA-windows-x64.zip
   dist\TORMENT_NEXUS-researchA-windows-x64.zip.partNN
   dist\REASSEMBLE_TORMENT_NEXUS-researchA-windows-x64.bat
   ```

4. Wrap every raw `.partNN` file with the streaming machinesoul builder:

   ```powershell
   python tools\machinesoul.py build `
     dist\TORMENT_NEXUS-researchA-windows-x64.zip.partNN `
     --out SABLERESEARCHA\package\TORMENT_NEXUS-researchA-windows-x64.zip.partNN.png
   ```

   A recipient must run `machinesoul.py` to recover the raw parts. Do not
   upload the raw `.zip.partNN` files: the public package layer is
   capsule-only.

5. Build the current optional 14B companion with:

   ```powershell
   python tools\package_model_pack.py
   ```

   Wrap every generated model `.partNN` with machinesoul. Do not upload the
   raw GGUF parts or raw model-pack metadata. The reviewed 14B model remains
   optional, but its researchA distribution follows the same capsule-only
   boundary as the main package.

6. Build `SABLE_researchA_research.png` from the Rosetta Stone tool, vector
   beam tool, anchor materials, their tests, and the two vector research
   papers. Build `SABLE_researchA_support.png` from:

   - the packager-generated main reassembler;
   - the 14B checksum-gated installer and its manifest/provenance records;
   - `SHA256SUMS_researchA.txt`.

   The support files must not also be uploaded raw.

7. Extract every completed capsule to a disposable output and compare the
   decoded size and SHA-256 with its raw source payload. Refuse the cut if any
   byte differs. Prove the decoded main parts rejoin to the archive SHA-256
   and the decoded 14B parts rejoin to the reviewed GGUF SHA-256.

8. Generate and test:

   - `DECOMPILE_SABLE_researchA.bat`, covering both support capsules, the
     exact main-package part count, and the optional 14B part count;
   - `SHA256SUMS_researchA.txt`, covering each downloaded capsule, decoded
     payload, plaintext bootstrap helper, complete ZIP, and complete GGUF;
   - the packager-generated reassembler, without hand-editing its part list.

9. Confirm the current release title and filenames in:

   - `README.md`;
   - `docs/INSTALL_WINDOWS.md`;
   - `docs/TROUBLESHOOTING.md`;
   - `docs/RELEASE_NOTES_researchA.md`;
   - `SABLERESEARCHA/RELEASE_BODY.md`.

10. Create GitHub release title/tag `researchA` as a draft. Upload:

   - every package `.partNN.png` capsule;
   - every optional 14B `.partNN.png` capsule;
   - `SABLE_researchA_research.png`;
   - `SABLE_researchA_support.png`;
   - `machinesoul.py`;
   - `DECOMPILE_SABLE_researchA.bat`.

   Those two plaintext files are the unavoidable decompiler bootstrap. Do
   not upload the raw reassembler, ledger, research files, ZIP/GGUF parts, or
   any other release payload.

11. Compare every GitHub asset's byte size and SHA-256 with the local file.
   Then download the remote capsules, decompile them, reassemble the remote
   package and 14B model, and compare the final ZIP/GGUF SHA-256 values with
   the local originals.

12. Inspect the draft release in the browser. Preserve the model, rights,
    privacy, safety, research-loss, and known-gap disclosures. Publish only
    after the operator explicitly approves the verified draft.

Allow about 55 GB of temporary free space when capsules, decoded parts, the
reconstructed ZIP, and the extracted package coexist. On a constrained build
drive, remove only reproducible intermediates after their hashes and remote
copies are verified.

Do not test `setup.bat` inside the final staged package and send that same
folder. Installer testing creates local runtime artifacts; rebuild and verify
a clean package afterward.
