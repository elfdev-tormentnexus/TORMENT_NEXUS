# TORMENT_NEXUS release checklist

This is a maintainer document, not an installation guide. Windows users should
follow [Installing on Windows](INSTALL_WINDOWS.md).

The Windows handoff is built from a clean source tree and intentionally keeps
personal runtime state out of the archive.

1. Run the source regression suite:

   ```powershell
   .\setup\test_assistant.bat
   ```

2. Build the archive:

   ```powershell
   python tools\package_release.py --archive --skip-download
   ```

3. Verify it:

   ```powershell
   python tools\package_release.py --verify-only
   ```

4. Split it for GitHub Releases and prove the numbered parts rejoin:

   ```powershell
   python tools\package_release.py --split
   ```

   This writes the versioned archive
   `dist\TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip`, numbered assets beginning
   with
   `dist\TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.zip.part01`, and the exact
   generated helper
   `dist\REASSEMBLE_TORMENT_NEXUS-v0.2.0-beta.6-windows-x64.bat`.
   Upload every generated numbered part and that helper; do not substitute the
   fixed source helper.

   On a drive that cannot hold the verified staged folder and a complete
   temporary split set simultaneously, use `--split --discard-stage` instead.
   It refuses unless the archive already exists, then removes only the
   rebuildable `dist\TORMENT_NEXUS` stage folder before splitting.
5. Build the required, separate 14B full-maintenance model pack:

   ```powershell
   python tools\package_model_pack.py
   python tools\package_model_pack.py --verify-only
   ```

   Upload every file from this exact versioned folder:

   `dist\modelpacks\TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b\`

   Its GitHub assets are:

   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.part01`;
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.part02`;
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.part03`;
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.part04`;
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.part05`;
   - `INSTALL_TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b.bat`;
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b-MANIFEST.json`;
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b-SHA256SUMS.txt`; and
   - `TORMENT_NEXUS-v0.2.0-beta.6-full-maintenance-14b-README.txt`.

   The packer rejects any source whose filename, byte size, or SHA-256 differs
   from the reviewed 14B artifact in `MODELS.md`. It does not overwrite an
   existing versioned output unless `--force` is explicit.
6. Record both manifests and checksum ledgers in the release notes. Preserve
   the unresolved 4B license disclosure and do not describe model availability
   as proof of redistribution permission.
7. Confirm the current release link and filenames in `README.md`,
   `docs/INSTALL_WINDOWS.md`, and `docs/TROUBLESHOOTING.md`.
8. Read the packaged `README.txt` and the model-pack README from a beginner's
   perspective and confirm
   its disk-space, first-launch, shortcut fallback, voice, music, and uninstall
   instructions still match the build.

Recipients must download every part into one folder, run the helper, validate
the reassembled ZIP checksum, then extract and run `setup.bat`.

Allow for about 40 GB of temporary free space when the main download parts,
reconstructed ZIP, and roughly 13 GB extracted folder are on the same drive.
Building the optional 14B asset set also needs room for the 8,988,111,200-byte
source plus a second split copy; do not start that build on a nearly full
drive.

Do not test `setup.bat` inside the final staged package and then send that same
folder. Installer testing creates local runtime artifacts; rebuild and verify a
fresh package afterward.

The package targets 64-bit Windows. Raspberry Pi deployment is a separate
validation target.
