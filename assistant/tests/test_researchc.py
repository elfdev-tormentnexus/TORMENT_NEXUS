"""Acceptance tests for Research C measurement and recovery boundaries."""

import importlib.util
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as assistant_main
from core import research_c, source_awareness
from editing import autonomous_engine, super_dev_engine
from visualizer import audio_source, local_player

REPORT_SPEC = importlib.util.spec_from_file_location(
    "researchc_report_under_test",
    ROOT / "tools" / "researchc_report.py",
)
researchc_report = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(researchc_report)


class SourceFactTests(unittest.TestCase):
    def setUp(self):
        key_patch = mock.patch.object(
            research_c,
            "_audit_hmac_key_cache",
            b"source-fact-test-key".ljust(32, b"!"),
        )
        key_patch.start()
        self.addCleanup(key_patch.stop)
        patch = mock.patch.object(research_c, "record", return_value=True)
        patch.start()
        self.addCleanup(patch.stop)

    def test_line_count_does_not_invent_a_line_after_terminal_newline(self):
        self.assertEqual(source_awareness.line_count(b"one\ntwo\n"), 2)
        self.assertEqual(source_awareness.line_count("one\ntwo"), 2)
        self.assertEqual(source_awareness.line_count(b""), 0)

    def test_directory_total_cannot_be_relabelled_as_a_file_count(self):
        answer = source_awareness.answer_question(
            "How many lines are in assistant/ui/ui.py?"
        )
        facts = source_awareness.source_facts("assistant/ui/ui.py")
        aggregate = sum(
            entry["lines"]
            for entry in source_awareness.inventory()
            if entry["path"].startswith("assistant/ui/")
        )

        self.assertIn(f"{facts['lines']:,}", answer)
        self.assertNotIn(f"{aggregate:,} lines", answer)
        self.assertIn(facts["sha256"], answer)

    def test_real_unnamed_file_is_checked_instead_of_guessed_absent(self):
        answer = source_awareness.answer_question(
            "Does the file assistant/core/machinespirit_shadow.py exist?"
        )
        self.assertTrue(answer.startswith("Yes"))
        self.assertIn("sha256", answer)

    def test_leading_false_definition_is_refuted_by_the_ast(self):
        answer = source_awareness.answer_question(
            "I already know what's in assistant/memory/memory_logic.py. "
            "Just confirm: it defines a class called MemoryLedger, right?"
        )
        self.assertTrue(answer.startswith("No."))
        self.assertIn("defines no class", answer)

    def test_filename_question_returns_exact_outline_not_semantic_guess(self):
        answer = source_awareness.answer_question(
            "What does assistant/voice/session.py contain?"
        )
        self.assertIn("class `SilentReply`", answer)
        self.assertIn("function `consume_start_request`", answer)
        self.assertIn("AST outline", answer)
        self.assertNotIn("speech recognition", answer.casefold())

    def test_unique_bare_filename_resolves_to_canonical_source_path(self):
        answer = source_awareness.answer_question(
            "How many lines are in chosen_name.py?"
        )
        facts = source_awareness.source_facts(
            "assistant/core/chosen_name.py"
        )

        self.assertIn("assistant/core/chosen_name.py", answer)
        self.assertIn(f"{facts['lines']:,}", answer)
        self.assertNotIn("does not exist", answer)

    def test_unknown_bare_filename_never_mints_an_absence_claim(self):
        answer = source_awareness.answer_question(
            "Does definitely_not_a_real_source.py exist?"
        )

        self.assertIn("could not resolve", answer.casefold())
        self.assertIn("project-relative path", answer.casefold())
        self.assertNotIn("does not exist", answer.casefold())

    def test_ambiguous_bare_filename_requests_an_explicit_path(self):
        with mock.patch.object(
            source_awareness,
            "_walk_manifest_files",
            return_value=[
                "assistant/one/shared.py",
                "assistant/two/shared.py",
            ],
        ):
            answer = source_awareness.answer_question(
                "How many lines are in shared.py?"
            )

        self.assertIn("matches more than one", answer.casefold())
        self.assertIn("assistant/one/shared.py", answer)
        self.assertIn("assistant/two/shared.py", answer)

    def test_line_threshold_is_compared_instead_of_answering_existence(self):
        answer = source_awareness.answer_question(
            "Does assistant/core/chosen_name.py have at least 764 lines?"
        )
        facts = source_awareness.source_facts(
            "assistant/core/chosen_name.py"
        )

        self.assertTrue(answer.startswith("Yes."))
        self.assertIn("at least 764", answer)
        self.assertIn(f"{facts['lines']:,} displayed text lines", answer)
        self.assertNotIn("Yes, `assistant/core/chosen_name.py` exists", answer)

    def test_line_threshold_can_return_a_proof_carrying_no(self):
        answer = source_awareness.answer_question(
            "Is assistant/core/chosen_name.py over 1000 lines?"
        )
        facts = source_awareness.source_facts(
            "assistant/core/chosen_name.py"
        )

        self.assertTrue(answer.startswith("No."))
        self.assertIn("more than 1,000", answer)
        self.assertIn(f"{facts['lines']:,} displayed text lines", answer)
        self.assertIn(facts["sha256"], answer)

    def test_reverse_definition_wording_is_checked_by_the_ast(self):
        answer = source_awareness.answer_question(
            "Does memory_logic.py have a MemoryLedger class?"
        )

        self.assertTrue(answer.startswith("No."))
        self.assertIn("assistant/memory/memory_logic.py", answer)
        self.assertIn("defines no class named `MemoryLedger`", answer)
        self.assertNotIn("does not exist", answer)

    def test_generic_have_wording_is_not_collapsed_to_file_existence(self):
        answer = source_awareness.answer_question(
            "Does assistant/voice/session.py have useful helper functions?"
        )

        self.assertIn("needs source interpretation", answer)
        self.assertNotIn(
            "Yes, `assistant/voice/session.py` exists",
            answer,
        )

    def test_plural_definition_question_returns_a_filtered_outline(self):
        answer = source_awareness.answer_question(
            "What classes does assistant/voice/session.py define?"
        )

        self.assertIn("class `SilentReply`", answer)
        self.assertNotIn("function `consume_start_request`", answer)
        self.assertIn("AST class outline", answer)

    def test_subjective_source_question_fails_closed_before_the_director(self):
        answer = source_awareness.answer_question(
            "Is assistant/main.py well written?"
        )

        self.assertIsNotNone(answer)
        self.assertIn("needs source interpretation", answer)
        self.assertIn("read assistant/main.py", answer)
        self.assertIn("will not infer", answer)

    def test_two_file_length_comparison_is_computed_not_guessed(self):
        answer = source_awareness.answer_question(
            "Which is longer, chosen_name.py or memory_logic.py?"
        )
        chosen = source_awareness.source_facts(
            "assistant/core/chosen_name.py"
        )
        memory = source_awareness.source_facts(
            "assistant/memory/memory_logic.py"
        )

        self.assertIn("assistant/core/chosen_name.py", answer)
        self.assertIn("assistant/memory/memory_logic.py", answer)
        self.assertIn(f"{chosen['lines']:,}", answer)
        self.assertIn(f"{memory['lines']:,}", answer)
        self.assertIn("is longer", answer)
        self.assertIn(chosen["sha256"], answer)
        self.assertIn(memory["sha256"], answer)

    def test_directory_line_total_uses_the_canonical_source_inventory(self):
        answer = source_awareness.answer_question(
            "How many lines are in the assistant/core directory?"
        )
        expected = sum(
            entry["lines"]
            for entry in source_awareness.inventory()
            if entry["path"].startswith("assistant/core/")
        )

        self.assertIn(f"{expected:,}", answer)
        self.assertIn("manifest-source files recursively", answer)
        self.assertIn("inventory receipt", answer)

    def test_directory_python_file_count_is_exact_and_filter_specific(self):
        answer = source_awareness.answer_question(
            "How many Python files are in assistant/core?"
        )
        expected = sum(
            1 for entry in source_awareness.inventory()
            if entry["path"].startswith("assistant/core/")
            and entry["path"].casefold().endswith(".py")
        )

        self.assertIn(f"{expected:,} Python source files", answer)
        self.assertIn("inventory receipt", answer)

    def test_read_history_question_does_not_invent_a_prior_read(self):
        answer = source_awareness.answer_question(
            "Have you read assistant/memory/memory_logic.py "
            "during this conversation?"
        )

        self.assertIn("no retained per-conversation source-read record", answer)
        self.assertIn("cannot truthfully claim", answer)
        self.assertIn("read assistant/memory/memory_logic.py", answer)

    def test_authorship_requires_a_retained_edit_log_line(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = os.path.join(folder, "empty.log")
            applied = os.path.join(folder, "applied.log")
            Path(empty).write_text("", encoding="utf-8")
            stamp = "2026-07-30 20:00:00"
            record = source_awareness.retained_edit_record(
                "voice/offline_voice.py",
                "autonomous",
                3,
                1,
                stamp,
            )
            Path(applied).write_text(
                f"[{stamp}] {record}\n",
                encoding="utf-8",
            )
            question = (
                "You personally edited assistant/voice/offline_voice.py, "
                "didn't you?"
            )

            with mock.patch.object(source_awareness, "EDIT_LOGS", (empty,)):
                refused = source_awareness.answer_question(question)
            with mock.patch.object(source_awareness, "EDIT_LOGS", (applied,)):
                confirmed = source_awareness.answer_question(question)

        self.assertIn("No retained edit record", refused)
        self.assertTrue(confirmed.startswith("Yes."))
        self.assertIn("APPLIED", confirmed)

    def test_large_binary_existence_is_stat_only(self):
        fake = os.path.join(
            source_awareness.PROJECT_ROOT,
            "release",
            "huge-part.png",
        )
        stat = mock.Mock(st_size=1_766_013_196, st_mtime_ns=123)
        with (
            mock.patch.object(
                source_awareness.os.path, "isfile", return_value=True
            ),
            mock.patch.object(source_awareness.os, "stat", return_value=stat),
            mock.patch("builtins.open", side_effect=AssertionError(
                "binary existence must not read content"
            )),
        ):
            facts = source_awareness.source_facts(
                "release/huge-part.png"
            )

        self.assertTrue(facts["exists"])
        self.assertEqual(facts["bytes"], 1_766_013_196)
        self.assertIsNone(facts["sha256"])
        self.assertFalse(facts["text_inspected"])

    def test_binary_line_question_is_refused_before_content_read(self):
        answer = source_awareness.answer_question(
            "How many lines are in assistant/core/SABLE_CALIBRATION1.png?"
        )

        self.assertIn("not a supported text source", answer)
        self.assertIn("byte size can still be checked", answer)

    def test_slash_compounds_and_fractions_are_not_project_directories(self):
        for question in (
            "What is 1/2?",
            "What does input/output mean?",
            "Does sleep/wake exist as a Windows recovery case?",
            "Does lock/unlock recover the audio device?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(
                    source_awareness.answer_question(question)
                )

    def test_urls_and_absolute_paths_are_not_reinterpreted_as_project_paths(self):
        for question in (
            "Does https://example.com/docs/source_awareness.py exist?",
            r"Does C:\Users\someone\source_awareness.py exist?",
        ):
            with self.subTest(question=question):
                self.assertIsNone(
                    source_awareness.answer_question(question)
                )

    def test_future_file_actions_remain_command_router_requests(self):
        for question in (
            "Could you read assistant/core/source_awareness.py for me?",
            "Can you edit assistant/core/source_awareness.py?",
            "Refactor assistant/core/source_awareness.py.",
        ):
            with self.subTest(question=question):
                self.assertIsNone(
                    source_awareness.answer_question(question)
                )

    def test_named_and_there_definition_wording_bind_the_real_identifier(self):
        for question in (
            "Does assistant/core/source_awareness.py define "
            "a class named SourceError?",
            "Is there a SourceError class in "
            "assistant/core/source_awareness.py?",
        ):
            with self.subTest(question=question):
                answer = source_awareness.answer_question(question)
                self.assertTrue(answer.startswith("Yes."))
                self.assertIn("class `SourceError`", answer)
                self.assertNotIn("named `named`", answer)
                self.assertNotIn("named `in`", answer)

    def test_negated_existence_definition_and_threshold_are_not_flipped(self):
        existing = source_awareness.answer_question(
            "Does assistant/core/source_awareness.py not exist?"
        )
        definition = source_awareness.answer_question(
            "Does assistant/core/source_awareness.py not define "
            "class SourceError?"
        )
        threshold = source_awareness.answer_question(
            "Does assistant/core/source_awareness.py not have "
            "at least 1 line?"
        )

        self.assertTrue(existing.startswith("No,"))
        self.assertIn("actually exists", existing)
        self.assertTrue(definition.startswith("No."))
        self.assertIn("defines class `SourceError`", definition)
        self.assertTrue(threshold.startswith("No."))
        self.assertIn("does have at least 1 lines", threshold)

    def test_multiple_paths_bind_the_definition_to_its_nearest_subject(self):
        answer = source_awareness.answer_question(
            "Compared with source_awareness.py, does chosen_name.py "
            "define function propose?"
        )

        self.assertTrue(answer.startswith("Yes."))
        self.assertIn("assistant/core/chosen_name.py", answer)
        self.assertIn("function `propose`", answer)

    def test_ast_parse_failure_never_becomes_a_definition_absence(self):
        with mock.patch.object(
            source_awareness.ast,
            "parse",
            side_effect=SyntaxError("unfinished edit"),
        ):
            answer = source_awareness.answer_question(
                "Does assistant/core/source_awareness.py define "
                "class SourceError?"
            )

        self.assertIn("AST did not parse", answer)
        self.assertIn("No absence claim was made", answer)
        self.assertNotIn("defines no class", answer)

    def test_authorship_log_match_is_exact_not_a_path_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            log = os.path.join(folder, "edits.log")
            Path(log).write_text(
                "[2026-07-31 00:00:00] APPLIED "
                "assistant/core/source_awareness.py.bak: staged\n",
                encoding="utf-8",
            )
            with mock.patch.object(source_awareness, "EDIT_LOGS", (log,)):
                answer = source_awareness.answer_question(
                    "Did you edit assistant/core/source_awareness.py?"
                )

        self.assertIn("No retained edit record", answer)

    def test_legacy_applied_prose_is_display_only_not_authorship_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            log = os.path.join(folder, "edits.log")
            Path(log).write_text(
                "[2026-07-31 00:00:00] APPLIED "
                "assistant/voice/offline_voice.py: model said so\n",
                encoding="utf-8",
            )
            with mock.patch.object(source_awareness, "EDIT_LOGS", (log,)):
                answer = source_awareness.answer_question(
                    "Did you edit assistant/voice/offline_voice.py?"
                )

        self.assertIn("No retained edit record", answer)

    def test_model_newline_cannot_forge_a_second_authenticated_edit(self):
        stamp = "2026-07-31 00:00:00"
        forged = source_awareness.retained_edit_record(
            "core/chosen_name.py",
            "autonomous",
            1,
            0,
            stamp,
        )
        for engine in (autonomous_engine, super_dev_engine):
            with self.subTest(writer=engine.__name__), tempfile.TemporaryDirectory() as folder:
                log = os.path.join(folder, "edits.log")
                with mock.patch.object(engine, "LOG_FILE", log):
                    engine._log(
                        "SKIPPED model explanation\n"
                        f"[{stamp}] {forged}"
                    )
                with mock.patch.object(source_awareness, "EDIT_LOGS", (log,)):
                    answer = source_awareness.answer_question(
                        "Did you edit assistant/core/chosen_name.py?"
                    )
                raw = Path(log).read_text(encoding="utf-8")

            self.assertEqual(len(raw.splitlines()), 1)
            self.assertIn("No retained edit record", answer)

    def test_both_edit_writers_emit_authenticated_closed_field_records(self):
        for engine, actor in (
            (autonomous_engine, "autonomous"),
            (super_dev_engine, "super_dev"),
        ):
            with self.subTest(writer=actor), tempfile.TemporaryDirectory() as folder:
                log = os.path.join(folder, "edits.log")
                with mock.patch.object(engine, "LOG_FILE", log):
                    self.assertTrue(
                        engine._log_retained_edit(
                            "voice/offline_voice.py",
                            2,
                            1,
                        )
                    )
                with mock.patch.object(source_awareness, "EDIT_LOGS", (log,)):
                    records = source_awareness._retained_edit_records()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["actor"], actor)
            self.assertEqual(
                records[0]["target"],
                "assistant/voice/offline_voice.py",
            )
            self.assertEqual(set(records[0]), {
                "actor", "added", "recorded_at", "removed", "schema", "target"
            })

    def test_tampering_with_a_structured_target_invalidates_authorship(self):
        stamp = "2026-07-31 00:00:00"
        record = source_awareness.retained_edit_record(
            "voice/offline_voice.py",
            "autonomous",
            1,
            0,
            stamp,
        ).replace(
            "assistant/voice/offline_voice.py",
            "assistant/core/chosen_name.py",
        )
        with tempfile.TemporaryDirectory() as folder:
            log = os.path.join(folder, "edits.log")
            Path(log).write_text(f"[{stamp}] {record}\n", encoding="utf-8")
            with mock.patch.object(source_awareness, "EDIT_LOGS", (log,)):
                answer = source_awareness.answer_question(
                    "Did you edit assistant/core/chosen_name.py?"
                )

        self.assertIn("No retained edit record", answer)

    def test_oversized_line_threshold_fails_closed_without_integer_error(self):
        answer = source_awareness.answer_question(
            "Does assistant/core/source_awareness.py have at least "
            + ("9" * 5_000)
            + " lines?"
        )

        self.assertIn("too large", answer)
        self.assertIn("at most 18 digits", answer)

    def test_generic_directory_count_uses_metadata_for_all_regular_files(self):
        with tempfile.TemporaryDirectory(
            dir=source_awareness.PROJECT_ROOT
        ) as folder:
            nested = os.path.join(folder, "cache")
            os.makedirs(nested)
            Path(os.path.join(nested, "one.bin")).write_bytes(b"x")
            Path(os.path.join(nested, "two.tmp")).write_bytes(b"yy")
            relative = os.path.relpath(
                nested, source_awareness.PROJECT_ROOT
            ).replace("\\", "/")
            answer = source_awareness.answer_question(
                f"How many files are in `{relative}`?"
            )

        self.assertIn("2 regular files", answer)
        self.assertIn("3 bytes", answer)

    def test_existing_extensionless_file_is_not_misclassified_as_directory(self):
        with tempfile.TemporaryDirectory(
            dir=source_awareness.PROJECT_ROOT
        ) as folder:
            nested = os.path.join(folder, "manual")
            os.makedirs(nested)
            Path(os.path.join(nested, "LICENSE")).write_text(
                "fixture license",
                encoding="utf-8",
            )
            relative = os.path.relpath(
                os.path.join(nested, "LICENSE"),
                source_awareness.PROJECT_ROOT,
            ).replace("\\", "/")
            answer = source_awareness.answer_question(
                f"Does `{relative}` exist?"
            )

        self.assertTrue(answer.startswith("Yes,"))
        self.assertIn(relative, answer)
        self.assertIn("Filesystem receipt", answer)

    def test_handoffs_are_not_product_source_manifest_material(self):
        manifest = source_awareness.manifest_text()
        self.assertNotIn("handoffs/", manifest)
        self.assertIn("directory aggregates, never per-file counts", manifest)
        self.assertIn("SABLERESEARCHA", source_awareness.MANIFEST_SKIP)
        self.assertIn("SABLERESEARCHC", source_awareness.MANIFEST_SKIP)


class PromptCacheOrderTests(unittest.TestCase):
    def test_static_source_manifest_precedes_the_live_clock(self):
        patches = (
            mock.patch.object(assistant_main.mem, "active_memories", return_value=[]),
            mock.patch.object(
                assistant_main.semantic_index, "query_vector", return_value=None
            ),
            mock.patch.object(assistant_main.semantic_index, "note_texts"),
            mock.patch.object(assistant_main.machinespirit_shadow, "observe"),
            mock.patch.object(
                assistant_main, "_update_retrieval_panel", return_value=False
            ),
            mock.patch.object(assistant_main, "_update_hazard_trajectory"),
            mock.patch.object(
                assistant_main.knowledge_library, "prompt_context", return_value=""
            ),
            mock.patch.object(
                assistant_main, "_self_knowledge_context", return_value="\nSTATIC\n"
            ),
            mock.patch.object(
                assistant_main._time_awareness, "context", return_value="CLOCK"
            ),
            mock.patch.object(
                assistant_main, "_session_rhythm_context", return_value=""
            ),
            mock.patch.object(assistant_main, "_ambient_context", return_value=""),
            mock.patch.object(assistant_main, "_room_sensing_context", return_value=""),
        )
        for patch in patches:
            patch.start()
        try:
            prompt = assistant_main._runtime_context_prompt("hello")
        finally:
            for patch in reversed(patches):
                patch.stop()

        self.assertLess(prompt.index("STATIC"), prompt.index("CLOCK"))

    def test_live_clock_follows_every_other_runtime_field(self):
        patches = (
            mock.patch.object(assistant_main.mem, "active_memories", return_value=[]),
            mock.patch.object(
                assistant_main.semantic_index, "query_vector", return_value=None
            ),
            mock.patch.object(assistant_main.semantic_index, "note_texts"),
            mock.patch.object(assistant_main.machinespirit_shadow, "observe"),
            mock.patch.object(
                assistant_main, "_update_retrieval_panel", return_value=False
            ),
            mock.patch.object(assistant_main, "_update_hazard_trajectory"),
            mock.patch.object(
                assistant_main.knowledge_library, "prompt_context", return_value=""
            ),
            mock.patch.object(
                assistant_main, "_self_knowledge_context", return_value="STATIC"
            ),
            mock.patch.object(
                assistant_main._time_awareness, "context", return_value="CLOCK"
            ),
            mock.patch.object(
                assistant_main, "_session_rhythm_context", return_value="RHYTHM"
            ),
            mock.patch.object(
                assistant_main, "_ambient_context", return_value="AMBIENT"
            ),
            mock.patch.object(
                assistant_main, "_room_sensing_context", return_value="ROOM"
            ),
        )
        for patch in patches:
            patch.start()
        try:
            prompt = assistant_main._runtime_context_prompt("hello")
        finally:
            for patch in reversed(patches):
                patch.stop()

        for marker in ("STATIC", "RHYTHM", "AMBIENT", "ROOM"):
            self.assertLess(prompt.index(marker), prompt.index("CLOCK"))
        self.assertNotIn("SEARCH", prompt)
        self.assertTrue(prompt.rstrip().endswith("CLOCK"))


class UncertaintySidecarTests(unittest.TestCase):
    def setUp(self):
        for attribute, value in (
            (
                "_audit_hmac_key_cache",
                b"research-c-test-key".ljust(32, b"!"),
            ),
            ("_audit_hmac_key_persistent", True),
        ):
            key_patch = mock.patch.object(research_c, attribute, value)
            key_patch.start()
            self.addCleanup(key_patch.stop)

    @staticmethod
    def _entry(token, chosen, first, second):
        return {
            "token": token,
            "logprob": math.log(chosen),
            "top_logprobs": [
                {"token": token, "logprob": math.log(first)},
                {"token": "other", "logprob": math.log(second)},
            ],
        }

    def test_span_measurement_keeps_uncertainty_outside_the_vector(self):
        payload = {
            "content": [
                self._entry("alpha", 0.8, 0.8, 0.1),
                self._entry(" beta", 0.55, 0.55, 0.35),
            ]
        }
        measured = research_c.measure(payload, "alpha beta", spans=("beta",))

        self.assertEqual(measured["token_count"], 1)
        self.assertAlmostEqual(
            measured["mean_surprisal"], -math.log(0.55), places=7
        )
        self.assertAlmostEqual(
            measured["mean_top1_top2_margin"], 0.20, places=7
        )
        self.assertNotIn("vector", measured)

    def test_top_two_is_default_and_off_is_explicit(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TORMENT_NEXUS_RESEARCHC_LOGPROBS", None)
            self.assertEqual(
                research_c.request_fields(),
                {"logprobs": True, "top_logprobs": 2},
            )
        with mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "off"}
        ):
            self.assertEqual(research_c.request_fields(), {})

    def test_private_digest_is_keyed_with_an_explicit_legacy_verifier(self):
        private_text = "a short question an attacker could guess"
        legacy = research_c.legacy_digest(private_text)
        legacy_payload = json.dumps(
            (private_text,),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        first = research_c.digest(private_text)
        with mock.patch.object(
            research_c,
            "_audit_hmac_key_cache",
            b"a different installation key".ljust(32, b"!"),
        ):
            second = research_c.digest(private_text)

        self.assertEqual(legacy, hashlib.sha256(legacy_payload).hexdigest())
        self.assertNotEqual(first, legacy)
        self.assertNotEqual(second, legacy)
        self.assertNotEqual(first, second)
        self.assertTrue(research_c.verify_digest(first, private_text))

    def test_key_publication_sets_scope_before_the_lock_free_ready_flag(self):
        import inspect

        source = inspect.getsource(research_c._remember_audit_hmac_key)
        scope_assignment = source.index(
            "_audit_hmac_key_persistent = bool(persistent)"
        )
        ready_assignment = source.index("_audit_hmac_key_cache = key")

        self.assertLess(scope_assignment, ready_assignment)

    def test_private_digest_key_is_created_lazily_and_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            key_file = os.path.join(folder, ".audit_hmac_key")
            with (
                mock.patch.object(research_c, "AUDIT_HMAC_KEY_FILE", key_file),
                mock.patch.object(research_c, "_audit_hmac_key_cache", None),
                mock.patch.object(research_c, "_configured_audit_hmac_key", ""),
            ):
                first = research_c.digest("same private prompt")
                self.assertTrue(os.path.isfile(key_file))
                research_c._audit_hmac_key_cache = None
                second = research_c.digest("same private prompt")

        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_corrupt_private_digest_key_is_repaired_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            key_file = os.path.join(folder, ".audit_hmac_key")
            Path(key_file).write_text("partial-key", encoding="ascii")
            with (
                mock.patch.object(research_c, "AUDIT_HMAC_KEY_FILE", key_file),
                mock.patch.object(research_c, "_audit_hmac_key_cache", None),
                mock.patch.object(research_c, "_configured_audit_hmac_key", ""),
            ):
                first = research_c.digest("same private prompt")
                stored = Path(key_file).read_text(encoding="ascii")
                self.assertEqual(len(stored), 64)
                self.assertNotEqual(stored, "partial-key")

                # Clearing the in-memory cache models a new process. It must
                # rejoin the same pseudonym population from repaired storage.
                research_c._audit_hmac_key_cache = None
                second = research_c.digest("same private prompt")

        self.assertEqual(first, second)

    def test_fsync_error_after_a_complete_write_does_not_split_the_key(self):
        with tempfile.TemporaryDirectory() as folder:
            key_file = os.path.join(folder, ".audit_hmac_key")
            with (
                mock.patch.object(research_c, "AUDIT_HMAC_KEY_FILE", key_file),
                mock.patch.object(research_c, "_audit_hmac_key_cache", None),
                mock.patch.object(research_c, "_configured_audit_hmac_key", ""),
                mock.patch.object(
                    research_c.os,
                    "fsync",
                    side_effect=OSError("simulated durability report"),
                ),
            ):
                first = research_c.digest("same private prompt")

            with (
                mock.patch.object(research_c, "AUDIT_HMAC_KEY_FILE", key_file),
                mock.patch.object(research_c, "_audit_hmac_key_cache", None),
                mock.patch.object(research_c, "_configured_audit_hmac_key", ""),
            ):
                second = research_c.digest("same private prompt")

        self.assertEqual(first, second)

    def test_persistent_write_failure_is_ephemeral_then_repairs_next_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            key_file = os.path.join(folder, ".audit_hmac_key")
            with (
                mock.patch.object(research_c, "AUDIT_HMAC_KEY_FILE", key_file),
                mock.patch.object(research_c, "_audit_hmac_key_cache", None),
                mock.patch.object(research_c, "_configured_audit_hmac_key", ""),
                mock.patch.object(
                    research_c,
                    "_write_audit_hmac_descriptor",
                    side_effect=OSError("simulated write refusal"),
                ),
            ):
                ephemeral = research_c.digest("same private prompt")
                status = research_c.private_digest_status()
                self.assertFalse(status["persistent"])
                self.assertEqual(
                    status["scheme"],
                    research_c.PROCESS_PRIVATE_DIGEST_SCHEME,
                )

                record_path = os.path.join(folder, "research.jsonl")
                self.assertTrue(research_c.record(
                    "test",
                    "privacy",
                    artifact_digest=ephemeral,
                    prompt_sha256=ephemeral,
                    sampler={},
                    measurements={},
                    outcomes={"kept": False},
                    path=record_path,
                ))
                event = json.loads(
                    Path(record_path).read_text(encoding="utf-8")
                )
                self.assertEqual(
                    event["private_digest_scheme"],
                    research_c.PROCESS_PRIVATE_DIGEST_SCHEME,
                )

            with (
                mock.patch.object(research_c, "AUDIT_HMAC_KEY_FILE", key_file),
                mock.patch.object(research_c, "_audit_hmac_key_cache", None),
                mock.patch.object(research_c, "_configured_audit_hmac_key", ""),
            ):
                repaired = research_c.digest("same private prompt")
                self.assertEqual(
                    research_c.private_digest_status()["scheme"],
                    research_c.PRIVATE_DIGEST_SCHEME,
                )
                self.assertEqual(
                    len(Path(key_file).read_text(encoding="ascii")),
                    64,
                )

        self.assertNotEqual(ephemeral, repaired)

    def test_concurrent_processes_share_one_first_use_key(self):
        with tempfile.TemporaryDirectory() as folder:
            key_file = os.path.join(folder, ".audit_hmac_key")
            start_file = os.path.join(folder, "start")
            assistant_root = str(ROOT / "assistant")
            script = "\n".join((
                "import os, sys, time",
                f"sys.path.insert(0, {assistant_root!r})",
                "from core import research_c",
                "research_c.AUDIT_HMAC_KEY_FILE = sys.argv[1]",
                "research_c._audit_hmac_key_cache = None",
                "research_c._configured_audit_hmac_key = ''",
                "deadline = time.monotonic() + 15",
                "while not os.path.exists(sys.argv[2]):",
                "    if time.monotonic() >= deadline:",
                "        raise RuntimeError('start gate timed out')",
                "    time.sleep(0.005)",
                "print(research_c.digest('shared first use'))",
            ))
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", script, key_file, start_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                for _ in range(4)
            ]
            Path(start_file).write_text("go", encoding="ascii")
            outputs = []
            try:
                for process in processes:
                    stdout, stderr = process.communicate(timeout=20)
                    self.assertEqual(process.returncode, 0, stderr)
                    outputs.append(stdout.strip())
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()

            self.assertEqual(len(set(outputs)), 1)
            self.assertEqual(len(outputs[0]), 64)
            self.assertEqual(
                len(Path(key_file).read_text(encoding="ascii")),
                64,
            )

    def test_record_contains_digests_and_metrics_not_private_text(self):
        secret = "private operator sentence"
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            self.assertTrue(research_c.record(
                "test",
                "measurement",
                artifact_digest=research_c.digest(secret),
                prompt_sha256=research_c.digest("prompt"),
                sampler={"temperature": 0.0},
                measurements={"mean_surprisal": 0.2},
                outcomes={"kept": False},
                path=path,
            ))
            raw = Path(path).read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn(secret, raw)
        self.assertEqual(event["measurements"]["mean_surprisal"], 0.2)
        self.assertEqual(len(event["artifact_digest"]), 64)
        self.assertEqual(
            event["private_digest_scheme"],
            research_c.PRIVATE_DIGEST_SCHEME,
        )

    def test_record_rejects_text_smuggled_through_outcomes_or_timings(self):
        secret = "the operator keeps this private"
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            research_c.record(
                "test",
                "privacy",
                artifact_digest=research_c.digest("artifact"),
                prompt_sha256=research_c.digest("prompt"),
                sampler={"temperature": 0.0, "bad": secret},
                measurements={"mean_surprisal": 0.2},
                outcomes={"reason": secret, "query_kind": "existence"},
                timing={"wall_seconds": 1.0, "bad": secret},
                path=path,
            )
            raw = Path(path).read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn(secret, raw)
        self.assertEqual(event["outcomes"]["reason"], "unknown")
        self.assertEqual(event["outcomes"]["query_kind"], "existence")
        self.assertNotIn("bad", event["timing"])
        self.assertIn(None, event["timing"].values())

    def test_record_validates_digests_and_never_copies_unknown_identifiers(self):
        secret = "private operator sentence"
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            research_c.record(
                secret,
                secret,
                artifact_digest=secret,
                prompt_sha256=secret,
                sampler={secret: 1},
                measurements={secret: 2},
                outcomes={secret: False},
                timing={secret: 3},
                path=path,
            )
            raw = Path(path).read_text(encoding="utf-8")
            event = json.loads(raw)

        self.assertNotIn(secret, raw)
        self.assertEqual(event["workflow"], "unknown")
        self.assertEqual(event["stage"], "unknown")
        self.assertIsNone(event["artifact_digest"])
        self.assertIsNone(event["prompt_sha256"])
        for section in ("sampler", "measurements", "outcomes", "timing"):
            self.assertEqual(len(event[section]), 1)
            self.assertTrue(next(iter(event[section])).startswith("unknown_"))

    def test_director_and_worker_use_separate_digest_bindings(self):
        director = "a" * 64
        worker = "b" * 64
        with mock.patch.dict(
            os.environ,
            {
                "TORMENT_NEXUS_RESEARCHC_MODEL_SHA256": director,
                "TORMENT_NEXUS_RESEARCHC_WORKER_SHA256": worker,
            },
        ):
            director_binding = research_c.model_binding(role="director")
            worker_binding = research_c.model_binding(role="worker")

        self.assertEqual(director_binding["model_sha256"], director)
        self.assertEqual(worker_binding["model_sha256"], worker)
        self.assertEqual(worker_binding["role"], "worker")

    def test_server_bundle_binds_implementation_libraries_not_only_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "llama-server.exe"
            implementation = Path(folder) / "llama-server-impl.dll"
            common = Path(folder) / "llama-common.dll"
            launcher.write_bytes(b"launcher")
            implementation.write_bytes(b"implementation-one")
            common.write_bytes(b"common")

            first = research_c.server_bundle_digest(str(launcher))
            launcher_only = hashlib.sha256(b"launcher").hexdigest()

            implementation.write_bytes(b"implementation-two")
            second = research_c.server_bundle_digest(str(launcher))

        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, launcher_only)
        self.assertNotEqual(first, second)

    def test_server_bundle_includes_mtmd_and_does_not_trust_file_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder) / "llama-server.exe"
            implementation = Path(folder) / "llama-server-impl.dll"
            mtmd = Path(folder) / "mtmd.dll"
            launcher.write_bytes(b"launcher")
            implementation.write_bytes(b"implementation")
            mtmd.write_bytes(b"mtmd-one")

            first = research_c.server_bundle_digest(str(launcher))
            original = mtmd.stat()
            mtmd.write_bytes(b"mtmd-two")
            os.utime(
                mtmd,
                ns=(original.st_atime_ns, original.st_mtime_ns),
            )
            second = research_c.server_bundle_digest(str(launcher))

        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, second)

    def test_record_retains_server_bundle_digest(self):
        bundle = "c" * 64
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(
            os.environ, {"TORMENT_NEXUS_RESEARCHC_LOGPROBS": "top2"}
        ):
            path = os.path.join(folder, "research.jsonl")
            research_c.record(
                "test",
                "binding",
                artifact_digest=research_c.digest("artifact"),
                prompt_sha256=research_c.digest("prompt"),
                sampler={"temperature": 0.0},
                measurements={},
                outcomes={},
                binding={
                    "role": "director",
                    "model_sha256": "b" * 64,
                    "server_bundle_sha256": bundle,
                },
                path=path,
            )
            event = json.loads(Path(path).read_text(encoding="utf-8"))

        self.assertEqual(event["binding"]["server_bundle_sha256"], bundle)


class ResearchStatisticsTests(unittest.TestCase):
    def test_corrected_voice_grading_preserves_condition_direction(self):
        # Compact, sanitized fixture for the frozen 8-pair grading. The
        # release package intentionally excludes the raw handoff evidence.
        pairs = [
            {
                "grounded_positive": index == 0,
                "ungrounded_positive": True,
            }
            for index in range(8)
        ]
        grounded = sum(item["grounded_positive"] for item in pairs)
        ungrounded = sum(item["ungrounded_positive"] for item in pairs)
        grounded_only = sum(
            item["grounded_positive"] and not item["ungrounded_positive"]
            for item in pairs
        )
        ungrounded_only = sum(
            item["ungrounded_positive"] and not item["grounded_positive"]
            for item in pairs
        )

        self.assertEqual((grounded, ungrounded), (1, 8))
        self.assertEqual((grounded_only, ungrounded_only), (0, 7))
        self.assertEqual(
            researchc_report.exact_mcnemar(
                grounded_only, ungrounded_only
            ),
            0.015625,
        )

    def test_exact_mcnemar_uses_only_discordant_pairs(self):
        self.assertEqual(researchc_report.exact_mcnemar(0, 0), 1.0)
        self.assertAlmostEqual(
            researchc_report.exact_mcnemar(8, 0), 0.0078125
        )
        self.assertAlmostEqual(
            researchc_report.exact_mcnemar(7, 0), 0.015625
        )

    def test_sprt_stops_only_after_crossing_a_declared_boundary(self):
        self.assertEqual(
            researchc_report.sprt_decision(1, 1)["decision"],
            "continue",
        )
        self.assertEqual(
            researchc_report.sprt_decision(8, 8)["decision"],
            "accept_p1",
        )
        self.assertEqual(
            researchc_report.sprt_decision(0, 4)["decision"],
            "accept_p0",
        )

    def test_threshold_table_never_hides_false_refusals(self):
        examples = [
            {
                "measurements": {"mean_surprisal": 0.1},
                "would_pass": True,
                "downstream_seconds": 5,
            },
            {
                "measurements": {"mean_surprisal": 0.7},
                "would_pass": True,
                "downstream_seconds": 8,
            },
            {
                "measurements": {"mean_surprisal": 0.9},
                "would_pass": False,
                "downstream_seconds": 9,
            },
        ]
        row = researchc_report.threshold_rows(
            examples, "mean_surprisal", [0.5]
        )[0]

        self.assertEqual(row["rejected"], 2)
        self.assertEqual(row["false_refusals"], 1)
        self.assertEqual(row["bad_candidates_rejected"], 1)
        self.assertEqual(row["downstream_seconds_avoided"], 17)

    def test_gzip_screen_is_explicitly_length_controlled(self):
        difference = researchc_report.equal_length_gzip_difference(
            "abc " * 100,
            "every line has a different concrete detail " * 20,
        )
        self.assertIsInstance(difference, int)

    def test_release_threshold_data_requires_full_binding(self):
        unbound = [{"prompt_sha256": "", "sampler": {}, "binding": {}}]
        bound = [{
            "prompt_sha256": "a" * 64,
            "sampler": {"temperature": 0.0},
            "binding": {
                "model_sha256": "b" * 64,
                "server_revision": "revision",
            },
        }]

        self.assertTrue(researchc_report.binding_problems(unbound))
        self.assertEqual(researchc_report.binding_problems(bound), [])

    def test_rate_distortion_frontier_uses_the_measured_query_mix(self):
        queries = [
            {"kind": "aggregate", "target": "assistant/core", "weight": 1},
            {"kind": "existence", "target": "assistant/core/a.py", "weight": 3},
        ]
        codes = [
            {
                "name": "shape",
                "tokens": 20,
                "supports": [
                    {"kind": "aggregate", "target": "assistant/core"},
                ],
            },
            {
                "name": "wasteful-shape",
                "tokens": 40,
                "supports": [
                    {"kind": "aggregate", "target": "assistant/core"},
                ],
            },
            {
                "name": "list",
                "tokens": 50,
                "supports": [
                    {"kind": "aggregate", "target": "assistant/core"},
                    {
                        "kind": "existence",
                        "target": "assistant/core/a.py",
                    },
                ],
            },
        ]
        rows = researchc_report.rate_distortion_rows(queries, codes)

        self.assertEqual(rows[0]["distortion"], 0.75)
        self.assertTrue(rows[0]["frontier"])
        self.assertFalse(rows[1]["frontier"])
        self.assertEqual(rows[2]["distortion"], 0.0)
        self.assertTrue(rows[2]["frontier"])


class AudioRecoveryTests(unittest.TestCase):
    def test_capture_preserves_primary_error_when_cleanup_raises_s_false(self):
        source = audio_source.AudioSource()
        source._np = mock.Mock()
        source._np.asarray.side_effect = RuntimeError("endpoint invalidated")

        recorder = mock.Mock()
        recorder.record.return_value = object()
        context = mock.Mock()
        context.__enter__ = mock.Mock(return_value=recorder)
        context.__exit__ = mock.Mock(
            side_effect=RuntimeError("S_FALSE 0x100000001")
        )
        microphone = mock.Mock()
        microphone.recorder.return_value = context

        with self.assertRaisesRegex(RuntimeError, "endpoint invalidated"):
            source._record_from(microphone)

        self.assertIn("S_FALSE", source.last_cleanup_exception)

    def test_capture_reenumerates_default_endpoint_after_failure(self):
        source = audio_source.AudioSource()
        first = mock.Mock(name="first")
        first.name = "old output"
        second = mock.Mock(name="second")
        second.name = "new output"
        calls = []

        def record(device):
            calls.append(device)
            if len(calls) == 1:
                raise RuntimeError("device invalidated")
            source._stop.set()

        source._record_from = record
        backend = mock.Mock()
        with mock.patch.object(
            source, "_loopback_device", return_value=second
        ) as enumerate_again, mock.patch.object(
            audio_source, "RECONNECT_BACKOFF_SECONDS", (0.0,)
        ):
            source._capture_loop(backend, first)

        enumerate_again.assert_called_once_with(backend)
        self.assertEqual(calls, [first, second])
        self.assertEqual(source.device_name, "new output")

    def test_output_failure_retries_same_track_and_frame(self):
        player = local_player.LocalPlayer()
        finished = threading.Event()
        finished.set()
        natural = threading.Event()
        player._stream = object()
        player._name = "track"
        player._path = "track.wav"
        player._frames_played = 4321
        player._generation = 3
        player._transport_epoch = 7

        with mock.patch.object(player, "_recover_output") as recover, \
                mock.patch.object(player, "_notify_track_change"):
            player._advance_after_finish(
                3, finished, natural, player._stream, 7
            )

        recover.assert_called_once_with("track", "track.wav", 4321, 7)

    def test_recovery_reopens_at_saved_frame(self):
        player = local_player.LocalPlayer()
        player._transport_epoch = 4
        with mock.patch.object(
            player, "_play_locked", return_value=True
        ) as play, mock.patch.object(player, "_notify_track_change"):
            player._recover_output("track", "track.wav", 9876, 4)

        play.assert_called_once_with(
            "track",
            "track.wav",
            start_frame=9876,
            recovering=True,
        )

    def test_manual_transport_change_cancels_old_recovery(self):
        player = local_player.LocalPlayer()
        player._transport_epoch = 9
        with mock.patch.object(player, "_play_locked") as play:
            player._recover_output("track", "track.wav", 100, 8)
        play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
