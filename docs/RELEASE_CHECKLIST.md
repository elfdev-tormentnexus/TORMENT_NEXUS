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

   This writes `dist\TORMENT_NEXUS.zip.part01` onward plus a matching
   `dist\REASSEMBLE_TORMENT_NEXUS.bat`. Upload every generated part and that
   generated helper; do not substitute the fixed source helper.

   On a drive that cannot hold the verified staged folder and a complete
   temporary split set simultaneously, use `--split --discard-stage` instead.
   It refuses unless the archive already exists, then removes only the
   rebuildable `dist\TORMENT_NEXUS` stage folder before splitting.
5. Record the archive's SHA-256 checksum and put the required filenames in
   the release notes.
6. Confirm the current release link and filenames in `README.md`,
   `docs/INSTALL_WINDOWS.md`, and `docs/TROUBLESHOOTING.md`.
7. Read the packaged `README.txt` from a beginner's perspective and confirm
   its disk-space, first-launch, shortcut fallback, voice, music, and uninstall
   instructions still match the build.

Recipients must download every part into one folder, run the helper, validate
the reassembled ZIP checksum, then extract and run `setup.bat`.

Allow for about 40 GB of temporary free space when the download parts,
reconstructed ZIP, and roughly 13 GB extracted folder are on the same drive.

Do not test `setup.bat` inside the final staged package and then send that same
folder. Installer testing creates local runtime artifacts; rebuild and verify a
fresh package afterward.

The package targets 64-bit Windows. Raspberry Pi deployment is a separate
validation target.
