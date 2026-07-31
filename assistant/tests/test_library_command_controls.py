"""Operator-facing controls for the opt-in semantic library backfill."""

import unittest
from unittest import mock

from commands import command_handlers
from knowledge import library


class LibrarySemanticCommandTests(unittest.TestCase):
    def setUp(self):
        self.dev_mode = command_handlers.DEV_MODE
        command_handlers.DEV_MODE = False

    def tearDown(self):
        command_handlers.DEV_MODE = self.dev_mode

    def _state(self, **changes):
        embedding = {
            "enabled": False,
            "eligible": 100,
            "eligible_sources": 80,
            "target": 50,
            "target_sources": 45,
            "embedded": 20,
            "embedded_sources": 18,
            "pending": 30,
            "due": 0,
            "backoff": 0,
            "quarantined": 0,
            "stored_current": 24,
            "out_of_target": 4,
            "coverage": 0.4,
            "complete": False,
            "stall_reason": "disabled",
        }
        embedding.update(changes)
        return {
            "enabled": True,
            "ready": True,
            "sources": 80,
            "chunks": 100,
            "embedded": embedding["embedded"],
            "errors": 0,
            "last_error": "",
            "semantic_warning": "",
            "trust_pending": 0,
            "user_library": "private",
            "embedding": embedding,
        }

    def test_status_exposes_target_coverage_and_disabled_default(self):
        with mock.patch.object(library, "status", return_value=self._state()):
            reply = command_handlers.handle_library("library semantic status")

        self.assertIn("Enabled: no", reply)
        self.assertIn("Fair target excerpts: 50", reply)
        self.assertIn("Covered target sources: 18", reply)
        self.assertIn("Out-of-target stored vectors: 4", reply)
        self.assertIn("State: disabled", reply)

    def test_enable_requires_developer_mode(self):
        with mock.patch.object(library, "set_embedding_enabled") as enabled:
            reply = command_handlers.handle_library("library semantic on")

        self.assertIn("requires developer mode", reply)
        enabled.assert_not_called()

    def test_developer_can_enable_and_disable_persistently(self):
        command_handlers.DEV_MODE = True

        with mock.patch.object(library, "set_embedding_enabled") as enabled:
            on_reply = command_handlers.handle_library("library semantic on")
            off_reply = command_handlers.handle_library("library semantic off")

        self.assertEqual(enabled.call_args_list, [mock.call(True), mock.call(False)])
        self.assertIn("fair target", on_reply)
        self.assertIn("Lexical library search remains active", off_reply)

    def test_quarantine_is_visible_without_enabling_backfill(self):
        report = {
            "quarantined": 1,
            "rows": [{
                "chunk_id": 42,
                "source": "manual.md",
                "heading": "Recovery",
                "attempts": 3,
                "last_error": "input was rejected",
            }],
        }

        with mock.patch.object(
            library,
            "embed_quarantine",
            return_value=report,
        ):
            reply = command_handlers.handle_library(
                "library semantic quarantine"
            )

        self.assertIn("Quarantined: 1", reply)
        self.assertIn("42: manual.md - Recovery", reply)
        self.assertIn("input was rejected", reply)

    def test_clear_only_accepts_a_positive_chunk_id_or_all(self):
        command_handlers.DEV_MODE = True

        with mock.patch.object(
            library,
            "clear_embed_quarantine",
            return_value=2,
        ) as clear:
            one = command_handlers.handle_library("library semantic clear 42")
            all_rows = command_handlers.handle_library(
                "library semantic clear all"
            )
            invalid = command_handlers.handle_library(
                "library semantic clear nope"
            )

        self.assertEqual(clear.call_args_list, [mock.call(42), mock.call(None)])
        self.assertIn("Cleared 2", one)
        self.assertIn("Cleared 2", all_rows)
        self.assertIn("<chunk-id>|all", invalid)


if __name__ == "__main__":
    unittest.main()
