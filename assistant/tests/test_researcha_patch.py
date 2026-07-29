"""Tests for the guarded direct machinesoul researchA patch installer."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "_researcha_patch_under_test",
    _ROOT / "tools" / "apply_researcha_patch.py",
)
patcher = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = patcher
_SPEC.loader.exec_module(patcher)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ResearchAPatchTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.target = self.folder / "TORMENT_NEXUS-researchA"
        self.payload = self.folder / "decoded-patch"
        self.target.mkdir()
        (self.payload / "payload" / "docs").mkdir(parents=True)

        self.before = b"finite claim before\n"
        self.after = b"finite claim corrected\n"
        (self.target / "docs").mkdir()
        (self.target / "docs" / "claim.md").write_bytes(self.before)
        (self.payload / "payload" / "docs" / "claim.md").write_bytes(
            self.after
        )
        self.application = {
            "format": patcher.FORMAT,
            "patch_id": "test-patch.1",
            "base_source_commit": "base",
            "patch_source_commit": "patched",
            "files": [{
                "path": "docs/claim.md",
                "before_sha256": digest(self.before),
                "after_sha256": digest(self.after),
                "after_bytes": len(self.after),
            }],
        }
        self.application_path = (
            self.payload / "PATCH_APPLICATION_MANIFEST.json"
        )
        self.application_path.write_text(
            json.dumps(self.application),
            encoding="utf-8",
        )
        release = {
            "format": 2,
            "files": [{
                "path": "docs/claim.md",
                "bytes": len(self.before),
                "sha256": digest(self.before),
            }],
        }
        (self.target / "RELEASE_MANIFEST.json").write_text(
            json.dumps(release),
            encoding="utf-8",
        )

    def apply(self):
        return patcher.apply_patch(
            str(self.target),
            str(self.payload),
            str(self.application_path),
        )

    def test_exact_base_is_backed_up_patched_and_recorded(self):
        result = self.apply()
        self.assertIn("applied", result)
        self.assertEqual(
            (self.target / "docs" / "claim.md").read_bytes(),
            self.after,
        )
        release = json.loads(
            (self.target / "RELEASE_MANIFEST.json").read_text("utf-8")
        )
        self.assertEqual(release["files"][0]["sha256"], digest(self.after))
        self.assertEqual(release["patches"][0]["id"], "test-patch.1")
        backups = list((self.target / "backups").glob("test-patch.1_*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            (backups[0] / "docs" / "claim.md").read_bytes(),
            self.before,
        )
        self.assertEqual(self.apply(), "already applied")

    def test_unknown_installed_file_is_refused_before_replacement(self):
        unknown = b"local edit that must survive\n"
        (self.target / "docs" / "claim.md").write_bytes(unknown)
        with self.assertRaises(patcher.PatchError):
            self.apply()
        self.assertEqual(
            (self.target / "docs" / "claim.md").read_bytes(),
            unknown,
        )
        self.assertFalse((self.target / "backups").exists())

    def test_escaping_manifest_path_is_refused(self):
        self.application["files"][0]["path"] = "../outside"
        self.application_path.write_text(
            json.dumps(self.application),
            encoding="utf-8",
        )
        with self.assertRaises(patcher.PatchError):
            self.apply()


if __name__ == "__main__":
    unittest.main()
