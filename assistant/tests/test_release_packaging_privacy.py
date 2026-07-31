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


class LlamaRuntimePackagingTests(unittest.TestCase):
    """Only the server's proven closure may enter a Windows release."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="torment-release-llama-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.stage = os.path.join(self.folder, "stage")
        self.runtime = os.path.join(self.folder, "neutral-runtime")
        os.makedirs(self.runtime)

    def _write_runtime(self):
        for name in package_release.LLAMA_RUNTIME_FILENAMES:
            Path(os.path.join(self.runtime, name)).write_bytes(
                ("runtime:" + name).encode("ascii")
            )

    def test_the_release_copies_only_the_proven_server_runtime_closure(self):
        self._write_runtime()
        Path(os.path.join(self.runtime, "llama-bench.exe")).write_bytes(
            b"not part of the server runtime"
        )

        with mock.patch.object(package_release, "ROOT", self.folder), \
                mock.patch.object(package_release, "STAGE", self.stage), \
                mock.patch.object(package_release, "INCLUDE_DIRS", []), \
                mock.patch.object(
                    package_release,
                    "INCLUDE_FILES",
                    list(package_release.LLAMA_RUNTIME_RELEASE_FILES),
                ), \
                mock.patch.object(
                    package_release,
                    "RELEASE_LLAMA_RUNTIME_DIR",
                    self.runtime,
                ), \
                mock.patch.dict(
                    os.environ,
                    {
                        "TORMENT_NEXUS_KNOWLEDGE_DIR": "",
                        "TORMENT_NEXUS_KNOWLEDGE_DB": "",
                    },
                    clear=False,
                ):
            package_release.stage([])

        destination = os.path.join(
            self.stage,
            *package_release.LLAMA_RUNTIME_DEST.split("/"),
        )
        self.assertEqual(
            {
                item.name
                for item in Path(destination).iterdir()
                if item.is_file()
            },
            set(package_release.LLAMA_RUNTIME_FILENAMES),
        )
        self.assertFalse(os.path.exists(os.path.join(
            destination,
            "llama-bench.exe",
        )))

    def test_a_missing_runtime_dependency_is_refused_before_stage_replacement(
            self):
        self._write_runtime()
        os.remove(os.path.join(
            self.runtime,
            package_release.LLAMA_RUNTIME_FILENAMES[-1],
        ))
        os.makedirs(self.stage)
        marker = os.path.join(self.stage, "known-good.txt")
        Path(marker).write_text("keep", encoding="utf-8")

        with mock.patch.object(package_release, "ROOT", self.folder), \
                mock.patch.object(package_release, "STAGE", self.stage), \
                mock.patch.object(package_release, "INCLUDE_DIRS", []), \
                mock.patch.object(
                    package_release,
                    "INCLUDE_FILES",
                    list(package_release.LLAMA_RUNTIME_RELEASE_FILES),
                ), \
                mock.patch.object(
                    package_release,
                    "RELEASE_LLAMA_RUNTIME_DIR",
                    self.runtime,
                ), \
                mock.patch.dict(
                    os.environ,
                    {
                        "TORMENT_NEXUS_KNOWLEDGE_DIR": "",
                        "TORMENT_NEXUS_KNOWLEDGE_DB": "",
                    },
                    clear=False,
                ):
            with self.assertRaisesRegex(
                package_release.ReleaseBuildError,
                "required llama-server runtime file is missing",
            ):
                package_release.stage([])

        self.assertTrue(os.path.isfile(marker))

    def test_binary_scan_rejects_checkout_and_profile_paths(self):
        os.makedirs(self.stage)
        checkout_binary = os.path.join(self.stage, "checkout.dll")
        profile_binary = os.path.join(self.stage, "profile.exe")
        profile = os.path.join(
            os.path.dirname(self.folder),
            "release-profile-marker",
        )
        Path(checkout_binary).write_bytes(
            b"prefix:" + os.path.realpath(self.folder).encode() + b":suffix"
        )
        Path(profile_binary).write_bytes(
            b"prefix:"
            + os.path.realpath(profile).lower().encode("utf-16le")
            + b":suffix"
        )

        with mock.patch.object(package_release, "ROOT", self.folder), \
                mock.patch.object(package_release, "STAGE", self.stage), \
                mock.patch.dict(
                    os.environ,
                    {"USERPROFILE": profile},
                    clear=False,
                ):
            report = []
            problems = []
            package_release._verify_no_local_binary_paths(report, problems)

        self.assertEqual(len(problems), 2)
        self.assertTrue(any(
            "local checkout" in problem and "checkout.dll" in problem
            for problem in problems
        ))
        self.assertTrue(any(
            "local user profile" in problem and "profile.exe" in problem
            for problem in problems
        ))
        self.assertIn("checked 2 staged binaries", "\n".join(report))

    def test_binary_scan_accepts_neutral_binaries_and_ignores_text(self):
        os.makedirs(self.stage)
        Path(os.path.join(self.stage, "neutral.dll")).write_bytes(
            b"path-neutral runtime"
        )
        Path(os.path.join(self.stage, "developer-note.txt")).write_text(
            os.path.realpath(self.folder),
            encoding="utf-8",
        )

        with mock.patch.object(package_release, "ROOT", self.folder), \
                mock.patch.object(package_release, "STAGE", self.stage), \
                mock.patch.dict(
                    os.environ,
                    {
                        "USERPROFILE": os.path.join(
                            self.folder,
                            "operator-profile",
                        )
                    },
                    clear=False,
                ):
            problems = []
            package_release._verify_no_local_binary_paths([], problems)

        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
