# TORMENT_NEXUS release checklist

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

4. Record the archive's SHA-256 checksum.
5. For GitHub Releases, split `dist/TORMENT_NEXUS.zip` into assets smaller
   than 2 GiB and upload the parts alongside `REASSEMBLE_TORMENT_NEXUS.bat`.
   Put the required filenames and full ZIP checksum in the release notes.

Recipients must download every part into one folder, run the helper, validate
the reassembled ZIP checksum, then extract and run `setup.bat`.

Do not test `setup.bat` inside the final staged package and then send that same
folder. Installer testing creates local runtime artifacts; rebuild and verify a
fresh package afterward.

The package targets 64-bit Windows. Raspberry Pi deployment is a separate
validation target.
