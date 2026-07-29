"""Focused tests for the versioned, exact-artifact model-pack builder."""

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))
_SPEC = importlib.util.spec_from_file_location(
    "package_model_pack_tests",
    os.path.join(_ROOT, "tools", "package_model_pack.py"),
)
package_model_pack = importlib.util.module_from_spec(_SPEC)
# dataclasses resolves annotation ownership through sys.modules while the
# module executes, so register this test-local name before exec_module.
sys.modules[_SPEC.name] = package_model_pack
_SPEC.loader.exec_module(package_model_pack)


class ModelPackTests(unittest.TestCase):
    DATA = b"0123456789abcdef"

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.output_root = os.path.join(self.folder, "output")
        self.model = os.path.join(self.folder, "reviewed-model.gguf")
        Path(self.model).write_bytes(self.DATA)
        self.spec = package_model_pack.ModelPackSpec(
            pack_id="test-pack",
            model_name="reviewed-model.gguf",
            size_bytes=len(self.DATA),
            sha256=hashlib.sha256(self.DATA).hexdigest().upper(),
            artifact_repository="https://huggingface.co/example/artifact",
            artifact_revision="a" * 40,
            derivative_repository="https://huggingface.co/example/derivative",
            declared_license="test-only",
        )

    def _build(self, **kwargs):
        return package_model_pack.build(
            self.model,
            output_root=self.output_root,
            spec=self.spec,
            max_asset_bytes=5,
            **kwargs,
        )

    def _verify(self):
        return package_model_pack.verify_output(
            output_root=self.output_root,
            spec=self.spec,
            max_asset_bytes=5,
        )

    def test_build_is_versioned_manifested_and_reconstructs_exact_bytes(self):
        output = self._build()
        manifest = self._verify()

        self.assertEqual(
            os.path.basename(output),
            f"TORMENT_NEXUS-{package_model_pack.RELEASE_VERSION}-test-pack",
        )
        self.assertEqual(manifest["release_version"], "researchA")
        self.assertEqual(manifest["model"]["sha256"], self.spec.sha256)
        self.assertEqual(
            manifest["provenance"]["artifact_revision"],
            "a" * 40,
        )

        parts = [
            item for item in manifest["files"]
            if item["kind"] == "part"
        ]
        self.assertEqual(len(parts), 4)
        reconstructed = b"".join(
            Path(output, item["name"]).read_bytes()
            for item in parts
        )
        self.assertEqual(reconstructed, self.DATA)
        self.assertTrue(all(item["size_bytes"] <= 5 for item in parts))

        self.assertTrue(Path(output, self.spec.installer_name).is_file())
        self.assertTrue(Path(output, self.spec.readme_name).is_file())
        self.assertTrue(Path(output, self.spec.manifest_name).is_file())
        self.assertTrue(Path(output, self.spec.checksums_name).is_file())

    def test_wrong_size_or_hash_is_rejected_before_output_is_created(self):
        wrong_size = package_model_pack.ModelPackSpec(
            **{
                **self.spec.__dict__,
                "size_bytes": len(self.DATA) + 1,
            }
        )
        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "wrong model size",
        ):
            package_model_pack.build(
                self.model,
                output_root=self.output_root,
                spec=wrong_size,
                max_asset_bytes=5,
            )
        self.assertFalse(os.path.exists(self.output_root))

        wrong_hash = package_model_pack.ModelPackSpec(
            **{
                **self.spec.__dict__,
                "sha256": "0" * 64,
            }
        )
        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "wrong model SHA-256",
        ):
            package_model_pack.build(
                self.model,
                output_root=self.output_root,
                spec=wrong_hash,
                max_asset_bytes=5,
            )

    def test_existing_output_requires_force_and_only_exact_target_is_replaced(self):
        output = self._build()
        marker = Path(output, "do-not-silently-delete.txt")
        marker.write_text("marker", encoding="utf-8")

        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "already exists",
        ):
            self._build()
        self.assertTrue(marker.exists())

        rebuilt = self._build(force=True)
        self.assertEqual(rebuilt, output)
        self.assertFalse(marker.exists())
        self._verify()

    def test_tampered_part_and_unexpected_file_both_fail_verification(self):
        output = self._build()
        manifest = json.loads(
            Path(output, self.spec.manifest_name).read_text(encoding="utf-8")
        )
        first_part = next(
            item["name"] for item in manifest["files"]
            if item["kind"] == "part"
        )
        Path(output, first_part).write_bytes(b"tampered")
        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "(size|SHA-256) mismatch",
        ):
            self._verify()

        self._build(force=True)
        Path(output, "stale-upload.bin").write_bytes(b"stale")
        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "unexpected files",
        ):
            self._verify()

    def test_non_regular_entry_and_reparse_manifest_are_rejected(self):
        output = self._build()
        unexpected = Path(output, "unexpected-directory")
        unexpected.mkdir()
        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "non-regular or reparse",
        ):
            self._verify()

        unexpected.rmdir()
        real_reparse_check = package_model_pack._is_reparse_point

        def mark_manifest(path):
            if os.path.basename(path) == self.spec.manifest_name:
                return True
            return real_reparse_check(path)

        with mock.patch.object(
            package_model_pack,
            "_is_reparse_point",
            side_effect=mark_manifest,
        ), self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "non-regular or reparse",
        ):
            self._verify()

    def test_installer_refuses_overwrite_and_contains_exact_hash(self):
        output = self._build()
        installer = Path(
            output,
            self.spec.installer_name,
        ).read_text(encoding="utf-8")

        self.assertIn(f'set "EXPECTED={self.spec.sha256}"', installer)
        self.assertIn("A DIFFERENT FILE ALREADY EXISTS", installer)
        self.assertIn("It was not overwritten", installer)
        self.assertNotIn("move /y", installer.lower())
        self.assertIn("Get-FileHash", installer)

    def test_unsafe_pack_metadata_is_rejected(self):
        unsafe = package_model_pack.ModelPackSpec(
            **{
                **self.spec.__dict__,
                "pack_id": "../escape",
            }
        )
        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "unsafe pack id",
        ):
            package_model_pack.build(
                self.model,
                output_root=self.output_root,
                spec=unsafe,
                max_asset_bytes=5,
            )

    def test_symlink_source_is_rejected_when_supported(self):
        link_folder = os.path.join(self.folder, "links")
        os.mkdir(link_folder)
        link = os.path.join(link_folder, self.spec.model_name)
        try:
            os.symlink(self.model, link)
        except (OSError, NotImplementedError):
            self.skipTest("file symlinks are not available")

        with self.assertRaisesRegex(
            package_model_pack.ModelPackError,
            "(symlink|reparse)",
        ):
            package_model_pack.build(
                link,
                output_root=self.output_root,
                spec=self.spec,
                max_asset_bytes=5,
            )


class ProductionModelPackContractTests(unittest.TestCase):
    def test_beta6_full_maintenance_identity_is_pinned(self):
        spec = package_model_pack.FULL_MAINTENANCE_14B

        self.assertEqual(package_model_pack.RELEASE_VERSION, "researchA")
        self.assertEqual(spec.size_bytes, 8_988_111_200)
        self.assertEqual(
            spec.sha256,
            "E89A7AE4E2B456BF33C75CFF35664751"
            "DF20FF273E551D7CF7640AA9E84D3B79",
        )
        self.assertEqual(
            spec.artifact_repository,
            "https://huggingface.co/bartowski/"
            "Qwen2.5-Coder-14B-Instruct-abliterated-GGUF",
        )
        self.assertIn(package_model_pack.RELEASE_VERSION, spec.asset_stem)
        self.assertEqual(
            package_model_pack._part_names(
                spec,
                spec.size_bytes,
                package_model_pack.MAX_ASSET_BYTES,
            ),
            tuple(
                f"{spec.asset_stem}.part{number:02d}"
                for number in range(1, 6)
            ),
        )


if __name__ == "__main__":
    unittest.main()
