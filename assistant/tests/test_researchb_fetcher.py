"""Tests for the post-cut, generated researchB capsule fetcher."""

import hashlib
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "researchb_fetcher_under_test", ROOT / "tools" / "build_researchb_fetcher.py"
)
fetcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetcher)


class ResearchBFetcherTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self._write("machinesoul.py")
        self._write("DECOMPILE_SABLE_researchB.bat")
        self._write("SABLERESEARCHB-MANIFEST.png")
        self._write("SABLERESEARCHB-REASSEMBLER.png")
        self._write("SABLERESEARCHB-WINDOWS.part01.png")
        self._write("SABLERESEARCHB-WINDOWS.part02.png")
        self._write("SABLERESEARCHB-14B.part01.png")

    def _write(self, name: str, content: bytes | None = None) -> Path:
        path = self.folder / name
        path.write_bytes(content if content is not None else name.encode("ascii"))
        return path

    def test_normal_fetcher_discovers_current_required_assets_and_digests(self):
        output = fetcher.build(self.folder)
        raw = output.read_bytes()
        text = raw.decode("ascii")

        self.assertEqual(output.name, "FETCH_SABLERESEARCHB.bat")
        self.assertIn(b"\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertIn("curl.exe --fail -L -C -", text)
        self.assertIn("certutil -hashfile", text)
        self.assertIn("DisableDelayedExpansion", text)
        self.assertIn("%NAME%.partial", text)
        self.assertIn("keeping the partial file for resume", text)
        self.assertIn("DECOMPILE_SABLE_researchB.bat", text)
        self.assertIn("SABLERESEARCHB-WINDOWS.part01.png", text)
        self.assertIn("SABLERESEARCHB-WINDOWS.part02.png", text)
        self.assertNotIn("SABLERESEARCHB-14B.part01.png", text)
        self.assertIn(
            hashlib.sha256(b"SABLERESEARCHB-WINDOWS.part01.png").hexdigest().upper(),
            text,
        )

    def test_optional_variant_only_includes_14b_when_explicitly_requested(self):
        output = fetcher.build(self.folder, include_optional_14b=True)
        text = output.read_text(encoding="ascii")

        self.assertEqual(output.name, "FETCH_SABLERESEARCHB_WITH_14B.bat")
        self.assertIn("SABLERESEARCHB-14B.part01.png", text)
        self.assertIn("explicitly includes the optional 14B", text)

    def test_gapped_or_malformed_primary_parts_are_refused(self):
        (self.folder / "SABLERESEARCHB-WINDOWS.part02.png").unlink()
        self._write("SABLERESEARCHB-WINDOWS.part03.png")
        with self.assertRaisesRegex(fetcher.FetcherError, "not consecutive"):
            fetcher.build(self.folder)

        (self.folder / "SABLERESEARCHB-WINDOWS.part03.png").unlink()
        self._write("SABLERESEARCHB-WINDOWS.preview.png")
        with self.assertRaisesRegex(fetcher.FetcherError, "unexpected"):
            fetcher.build(self.folder)

    def test_missing_bootstrap_and_unsafe_tag_are_refused_without_a_fetcher(self):
        (self.folder / "machinesoul.py").unlink()
        with self.assertRaisesRegex(fetcher.FetcherError, "machinesoul.py"):
            fetcher.build(self.folder)
        self.assertFalse((self.folder / fetcher.DEFAULT_FETCHER_NAME).exists())

        self._write("machinesoul.py")
        with self.assertRaisesRegex(fetcher.FetcherError, "unsafe GitHub release tag"):
            fetcher.build(self.folder, tag="researchB/unsafe")
        self.assertFalse((self.folder / fetcher.DEFAULT_FETCHER_NAME).exists())

    def test_output_cannot_be_redirected_away_from_the_verified_assets(self):
        elsewhere = self.folder.parent / "FETCH_SABLERESEARCHB.bat"
        with self.assertRaisesRegex(fetcher.FetcherError, "beside the release assets"):
            fetcher.build(self.folder, out_path=elsewhere)

    @unittest.skipUnless(os.name == "nt", "executes the generated Windows batch")
    def test_generated_batch_resumes_in_a_path_containing_bang(self):
        if not shutil.which("curl.exe") or not shutil.which("certutil.exe"):
            self.skipTest("Windows curl.exe and certutil.exe are required")

        output = fetcher.build(self.folder)
        destination = self.folder.parent / (self.folder.name + " download!field")
        destination.mkdir()
        self.addCleanup(shutil.rmtree, destination, True)
        batch = destination / output.name

        github_base = (
            f"https://github.com/{fetcher.REPOSITORY}/releases/download/"
            f"{fetcher.RELEASE_VERSION}"
        )
        text = output.read_text(encoding="ascii").replace(
            github_base, self.folder.as_uri()
        )
        batch.write_text(text, encoding="ascii", newline="")

        # This is the state left by an interrupted earlier invocation.  The
        # next one must resume it, not erase it before curl sees it.
        asset = self.folder / "machinesoul.py"
        partial = destination / "machinesoul.py.partial"
        partial.write_bytes(asset.read_bytes()[:5])
        complete_but_wrong = destination / "DECOMPILE_SABLE_researchB.bat.partial"
        complete_but_wrong.write_bytes(
            b"X" * (self.folder / "DECOMPILE_SABLE_researchB.bat").stat().st_size
        )
        damaged_target = destination / "SABLERESEARCHB-MANIFEST.png"
        damaged_target.write_bytes(b"damaged")

        result = subprocess.run(
            ["cmd.exe", "/d", "/c", str(batch)],
            cwd=destination,
            input=b"\r\n\r\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        transcript = result.stdout.decode("utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, transcript)
        self.assertIn("resuming existing 5-byte partial file", transcript)
        self.assertIn("complete-size partial failed verification", transcript)
        self.assertIn("checksum mismatch; removing damaged file", transcript)

        for name, _size, _digest in fetcher.discover_assets(self.folder):
            self.assertEqual(
                (destination / name).read_bytes(),
                (self.folder / name).read_bytes(),
                name,
            )
            self.assertFalse((destination / f"{name}.partial").exists(), name)


if __name__ == "__main__":
    unittest.main()
