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

4. Share only `dist/TORMENT_NEXUS.zip` and its SHA-256 checksum.

Do not test `setup.bat` inside the final staged package and then send that same
folder. Installer testing creates local runtime artifacts; rebuild and verify a
fresh package afterward.

The package targets 64-bit Windows. Raspberry Pi deployment is a separate
validation target.
