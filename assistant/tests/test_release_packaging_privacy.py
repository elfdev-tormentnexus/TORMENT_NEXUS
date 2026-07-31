"""Privacy boundaries for the release packager."""

import importlib.util
import json
import os
from pathlib import Path
import re
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


class SanitizedResearchHandoffPackagingTests(unittest.TestCase):
    def test_only_the_reviewed_librarian_derivative_is_whitelisted(self):
        expected = {
            "handoffs/researchc_librarian_2026-07-31/README.md",
            "handoffs/researchc_librarian_2026-07-31/result.json",
            (
                "handoffs/researchc_librarian_2026-07-31/"
                "shipped_director_followup_spec.json"
            ),
            (
                "handoffs/researchc_librarian_2026-07-31/"
                "shipped_director_followup_result.json"
            ),
        }
        packaged_handoffs = {
            path for path in package_release.INCLUDE_FILES
            if path.startswith("handoffs/")
        }

        self.assertEqual(
            set(package_release.LIBRARIAN_HANDOFF_FILES),
            expected,
        )
        self.assertEqual(packaged_handoffs, expected)

    def test_librarian_derivative_contains_no_host_path_or_raw_material(self):
        texts = {}
        for relative in package_release.LIBRARIAN_HANDOFF_FILES:
            text = Path(_ROOT, *relative.split("/")).read_text(
                encoding="utf-8"
            )
            texts[relative] = text
            self.assertIsNone(
                re.search(r"(?i)\b[a-z]:[\\/]", text),
                relative,
            )
            self.assertIsNone(
                re.search(r"(?i)\bbearer\s+[a-z0-9._~-]{16,}", text),
                relative,
            )

        first_result = json.loads(texts[
            "handoffs/researchc_librarian_2026-07-31/result.json"
        ])
        followup_result = json.loads(texts[
            "handoffs/researchc_librarian_2026-07-31/"
            "shipped_director_followup_result.json"
        ])
        for result in (first_result, followup_result):
            self.assertTrue(result["privacy"])
            self.assertFalse(any(result["privacy"].values()))
            self.assertEqual(
                result["disposition"],
                "shadow_only_not_promoted",
            )

        self.assertEqual(
            first_result["librarian"]["parse_validity"],
            11 / 16,
        )
        self.assertEqual(first_result["librarian"]["task_accuracy"], 9 / 16)
        self.assertEqual(first_result["librarian"]["order_agreement"], 1 / 8)
        self.assertEqual(followup_result["parse_validity"], 15 / 16)
        self.assertEqual(followup_result["task_accuracy"], 9 / 16)
        self.assertEqual(followup_result["order_agreement"], 5 / 8)
        self.assertFalse(followup_result["librarian_gate_passed"])

    def test_stage_copies_all_reviewed_handoff_files_and_nothing_else(self):
        with tempfile.TemporaryDirectory(
            prefix="torment-librarian-handoff-"
        ) as folder, mock.patch.object(
            package_release,
            "STAGE",
            os.path.join(folder, "stage"),
        ), mock.patch.object(
            package_release,
            "INCLUDE_DIRS",
            [],
        ), mock.patch.object(
            package_release,
            "INCLUDE_FILES",
            list(package_release.LIBRARIAN_HANDOFF_FILES),
        ), mock.patch.dict(
            os.environ,
            {
                "TORMENT_NEXUS_KNOWLEDGE_DIR": "",
                "TORMENT_NEXUS_KNOWLEDGE_DB": "",
            },
            clear=False,
        ):
            copied, skipped = package_release.stage([])
            destination = Path(
                package_release.STAGE,
                "handoffs",
                "researchc_librarian_2026-07-31",
            )
            self.assertEqual(copied, 4)
            self.assertEqual(skipped, 0)
            self.assertEqual(
                {path.name for path in destination.iterdir()},
                {
                    "README.md",
                    "result.json",
                    "shipped_director_followup_spec.json",
                    "shipped_director_followup_result.json",
                },
            )

    def test_unreviewed_cardiac_draft_is_not_a_public_release_input(self):
        self.assertNotIn(
            "docs/review_candidates/CARDIAC_ARREST_CPR_AED.md",
            package_release.INCLUDE_FILES,
        )


class RootDisclosurePackagingTests(unittest.TestCase):
    def test_keyword_named_untracked_bait_is_not_discovered(self):
        with tempfile.TemporaryDirectory(
            prefix="torment-root-disclosure-"
        ) as folder:
            Path(folder, "PRIVACY.md").write_text(
                "reviewed public disclosure",
                encoding="utf-8",
            )
            Path(folder, "SECURITY_PRIVATE_NOTES.md").write_text(
                "untracked maintainer material",
                encoding="utf-8",
            )
            Path(folder, "MODEL_SECRETS.txt").write_text(
                "ignored maintainer material",
                encoding="utf-8",
            )

            self.assertEqual(
                package_release._existing_optional_root_documents(folder),
                ("PRIVACY.md",),
            )


class PrivateRuntimeArtifactTests(unittest.TestCase):
    def test_every_known_private_credential_has_all_three_guards(self):
        names = {
            ".model_api_key",
            ".audit_hmac_key",
            ".dev_passcode",
            ".super_dev_passcode",
            ".tdeck_ble_pin",
            ".spotify_token",
            ".agent_token",
            ".anthropic_api_key",
            ".openai_api_key",
        }

        for name in names:
            relative = "assistant/" + name
            with self.subTest(name=name):
                self.assertTrue(package_release.denied(relative))
                self.assertTrue(package_release.private_basename(name))
                self.assertIn(relative, package_release.RUNTIME_ARTIFACTS)


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

    def test_every_prompt_cache_profile_is_denylisted(self):
        for path in (
            "assistant/cache/prompt/cache.bin",
            "assistant/cache/prompt-desktop/cache.bin",
            "assistant/cache/prompt-super-dev/cache.bin.tmp",
        ):
            with self.subTest(path=path):
                self.assertTrue(package_release.denied(path))

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

    def test_path_scans_accept_neutral_binary_but_reject_leaking_text(self):
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
            package_release._verify_no_local_text_paths([], problems)

        self.assertEqual(len(problems), 1)
        self.assertIn("staged text embeds the local checkout path", problems[0])
        self.assertIn("developer-note.txt", problems[0])


if __name__ == "__main__":
    unittest.main()
