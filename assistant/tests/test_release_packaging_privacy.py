"""Privacy boundaries for the Beta 6 release packager."""

import importlib.util
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))
_SPEC = importlib.util.spec_from_file_location(
    "package_release_privacy_tests",
    os.path.join(_ROOT, "tools", "package_release.py"),
)
package_release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(package_release)


class TrackedSourcePackagingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="torment-release-privacy-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.stage = os.path.join(self.folder, "stage")
        self.assistant = os.path.join(self.folder, "assistant")
        self.vendor = os.path.join(self.folder, "vendor")
        os.makedirs(self.assistant)
        os.makedirs(self.vendor)

        Path(os.path.join(self.assistant, "tracked.py")).write_text(
            "TRACKED = True\n",
            encoding="utf-8",
        )
        Path(os.path.join(self.assistant, "private-notes.txt")).write_text(
            "operator-only material",
            encoding="utf-8",
        )
        Path(os.path.join(self.vendor, "runtime.bin")).write_bytes(
            b"explicit runtime input"
        )

    def _patch_inputs(self):
        return (
            mock.patch.object(package_release, "ROOT", self.folder),
            mock.patch.object(package_release, "STAGE", self.stage),
            mock.patch.object(
                package_release,
                "INCLUDE_DIRS",
                [("assistant", "assistant"), ("vendor", "vendor")],
            ),
            mock.patch.object(package_release, "INCLUDE_FILES", []),
            mock.patch.object(
                package_release,
                "TRACKED_ONLY_DIRS",
                {"assistant"},
            ),
            mock.patch.dict(
                os.environ,
                {
                    "TORMENT_NEXUS_KNOWLEDGE_DIR": "",
                    "TORMENT_NEXUS_KNOWLEDGE_DB": "",
                },
                clear=False,
            ),
        )

    def test_untracked_assistant_files_are_not_copied_but_vendor_tree_is(self):
        git_result = SimpleNamespace(
            returncode=0,
            stdout="assistant/tracked.py\0",
            stderr="",
        )
        patches = self._patch_inputs()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
                patches[5], mock.patch.object(
                    package_release,
                    "_git",
                    return_value=git_result,
                ):
            package_release.stage([])

        self.assertTrue(os.path.isfile(os.path.join(
            self.stage, "assistant", "tracked.py"
        )))
        self.assertFalse(os.path.exists(os.path.join(
            self.stage, "assistant", "private-notes.txt"
        )))
        self.assertTrue(os.path.isfile(os.path.join(
            self.stage, "vendor", "runtime.bin"
        )))

    def test_missing_git_inventory_never_falls_back_to_recursive_copy(self):
        git_result = SimpleNamespace(
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )
        patches = self._patch_inputs()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
                patches[5], mock.patch.object(
                    package_release,
                    "_git",
                    return_value=git_result,
                ):
            with self.assertRaisesRegex(
                package_release.ReleaseBuildError,
                "tracked-file inventory.*refusing to recursively copy",
            ):
                list(package_release._included_source_files())

    def test_empty_git_inventory_is_an_error_not_a_recursive_fallback(self):
        git_result = SimpleNamespace(returncode=0, stdout="", stderr="")
        patches = self._patch_inputs()
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
                patches[5], mock.patch.object(
                    package_release,
                    "_git",
                    return_value=git_result,
                ):
            with self.assertRaisesRegex(
                package_release.ReleaseBuildError,
                "no tracked files.*recursive-copy fallback",
            ):
                list(package_release._included_source_files())


class ConfiguredKnowledgePathPackagingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="torment-release-knowledge-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        os.makedirs(os.path.join(self.folder, "assistant"))
        os.makedirs(os.path.join(self.folder, "vendor"))

    def _assert_refused(self, variable, value):
        environment = {
            "TORMENT_NEXUS_KNOWLEDGE_DIR": "",
            "TORMENT_NEXUS_KNOWLEDGE_DB": "",
            variable: value,
        }
        with mock.patch.object(package_release, "ROOT", self.folder), \
                mock.patch.object(
                    package_release,
                    "INCLUDE_DIRS",
                    [("assistant", "assistant"), ("vendor", "vendor")],
                ), \
                mock.patch.object(package_release, "INCLUDE_FILES", []), \
                mock.patch.dict(os.environ, environment, clear=False):
            with self.assertRaisesRegex(
                package_release.ReleaseBuildError,
                variable + " points .* inside the release input tree",
            ):
                package_release._validate_configured_private_paths()

    def test_relative_custom_library_inside_assistant_is_refused(self):
        self._assert_refused(
            "TORMENT_NEXUS_KNOWLEDGE_DIR",
            os.path.join("assistant", "private-library"),
        )

    def test_custom_database_inside_recursive_vendor_tree_is_refused(self):
        self._assert_refused(
            "TORMENT_NEXUS_KNOWLEDGE_DB",
            os.path.join(self.folder, "vendor", "private.sqlite3"),
        )

    def test_custom_library_containing_an_input_tree_is_also_refused(self):
        self._assert_refused(
            "TORMENT_NEXUS_KNOWLEDGE_DIR",
            self.folder,
        )

    def test_private_paths_outside_release_inputs_are_allowed(self):
        private = os.path.join(
            os.path.dirname(self.folder),
            os.path.basename(self.folder) + "-private",
        )
        environment = {
            "TORMENT_NEXUS_KNOWLEDGE_DIR": private,
            "TORMENT_NEXUS_KNOWLEDGE_DB": os.path.join(
                private,
                "library.sqlite3",
            ),
        }
        with mock.patch.object(package_release, "ROOT", self.folder), \
                mock.patch.object(
                    package_release,
                    "INCLUDE_DIRS",
                    [("assistant", "assistant"), ("vendor", "vendor")],
                ), \
                mock.patch.object(package_release, "INCLUDE_FILES", []), \
                mock.patch.dict(os.environ, environment, clear=False):
            package_release._validate_configured_private_paths()


if __name__ == "__main__":
    unittest.main()
