from collections import Counter
import inspect
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import main as assistant_main
from commands import command_handlers
from commands import natural_command
from core import config
from core import dev_auth
from core import file_utils
from core import health_check
from core import llm_server
from core import persona
from core import tutorial
from core.stream_filter import StreamFilter
from editing import edit_guard
from editing import edit_generator
from editing import edit_engine
from editing import goal_engine
from editing import autonomous_engine
from editing import self_heal_state
from hardware import tdeck
from memory import memory_worker
from memory import memory_extractor
from memory import memory_logic
from project import project_analyzer
from project import project_builder
from ui import ui
from voice import offline_voice
from voice import session as voice_session
from visualizer import local_player
from visualizer import music_metadata
from visualizer import spotify_control
from visualizer.radial import RadialVisualizer
from visualizer.spectrum import SpectrumVisualizer
from visualizer.reactor import ReactorVisualizer

# The desktop icon animator lives beside the assistant package, not in it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "tools"))
import glitch_icon
from web import search_engine


class PathSafetyGuardTests(unittest.TestCase):
    def test_edit_guard_denylist_is_case_insensitive(self):
        for path in (
            "MAIN.py",
            "Core/Config.py",
            "CORE/llm_server.py",
            "core/dev_auth.py",
            "core/file_utils.py",
            "EDITING/edit_guard.py",
            "COMMANDS/natural_command.py",
            "PROJECT/project_builder.py",
            "VOICE/setup_voice.py",
            "UI/ui.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(edit_guard.GuardError):
                    edit_guard.resolve(path)

    def test_autonomous_edits_use_a_smaller_allowlist(self):
        allowed = edit_guard.list_autonomous_files()

        self.assertIn("memory/memory_logic.py", allowed)
        self.assertNotIn("ui/ui.py", allowed)
        self.assertNotIn("core/persona.py", allowed)
        self.assertNotIn("web/search_engine.py", allowed)

    def test_autonomous_edit_cannot_add_process_execution(self):
        original = "def render():\n    return 'ready'\n"
        updated = (
            "import subprocess\n\n"
            "def render():\n"
            "    return subprocess.run(['whoami'])\n"
        )

        problem = edit_guard.autonomous_change_problem(
            "memory/memory_logic.py",
            original,
            updated,
        )

        self.assertIn("protected", problem)

    def test_autonomous_edit_can_make_a_pure_local_change(self):
        problem = edit_guard.autonomous_change_problem(
            "memory/memory_logic.py",
            "def label():\n    return 'old'\n",
            "def label():\n    return 'clearer'\n",
        )

        self.assertIsNone(problem)

class AutonomousSerialTests(unittest.TestCase):
    def setUp(self):
        self.original_applied = autonomous_engine._applied_this_run
        autonomous_engine._applied_this_run = 0
        self.addCleanup(self._restore_applied)

    def _restore_applied(self):
        autonomous_engine._applied_this_run = self.original_applied

    def test_observed_serial_is_capped_at_three_successful_edits(self):
        suggestion = {
            "title": "small repair",
            "file": "memory/memory_logic.py",
            "change": "small local change",
        }

        def apply_one(_suggestion):
            autonomous_engine._applied_this_run += 1
            return f"edit {autonomous_engine._applied_this_run}"

        with mock.patch.object(
            autonomous_engine.suggestion_engine,
            "generate",
            return_value=([suggestion], None),
        ), mock.patch.object(
            autonomous_engine,
            "_try_apply",
            side_effect=apply_one,
        ) as apply, mock.patch.object(autonomous_engine, "_log"):
            summaries = autonomous_engine.run_observed_serial()

        self.assertEqual(summaries, ["edit 1", "edit 2", "edit 3"])
        self.assertEqual(apply.call_count, autonomous_engine.OBSERVED_SERIAL_LIMIT)


class SelfHealRewardTests(unittest.TestCase):
    def test_validation_requires_health_and_the_fixed_regression_run(self):
        completed = SimpleNamespace(returncode=0, stdout="tests ok", stderr="")

        with mock.patch.object(
            self_heal_state.health_check,
            "report",
            return_value="ASSISTANT HEALTH CHECK\nOverall: healthy",
        ), mock.patch.object(
            self_heal_state.subprocess,
            "run",
            return_value=completed,
        ) as run:
            healthy, detail = self_heal_state.validate_restart()

        self.assertTrue(healthy)
        self.assertIn("passed", detail)
        self.assertEqual(run.call_args.args[0][1:4], ["-m", "unittest", "discover"])

    def test_clean_batch_spends_exactly_one_bonus_credit_after_validation(self):
        state = {
            "phase": self_heal_state.PHASE_VALIDATE_BATCH,
            "records": [{"target": "memory/memory_logic.py", "backup": "x.bak"}],
        }
        record = {
            "target": "memory/memory_logic.py",
            "backup": "bonus.bak",
        }

        with mock.patch.object(
            self_heal_state,
            "load",
            return_value=state,
        ), mock.patch.object(
            self_heal_state,
            "validate_restart",
            return_value=(True, "Health check and regression validation passed."),
        ), mock.patch.object(
            autonomous_engine,
            "run_cycle",
            return_value="APPLIED bonus",
        ) as cycle, mock.patch.object(
            autonomous_engine,
            "last_applied_record",
            return_value=record,
        ), mock.patch.object(self_heal_state, "begin_bonus_validation") as mark:
            message, reload_needed = assistant_main._resume_earned_self_heal_reward()

        cycle.assert_called_once_with()
        mark.assert_called_once_with(record)
        self.assertTrue(reload_needed)
        self.assertIn("BONUS APPLIED", message)

    def test_failed_validation_restores_the_batch_and_withholds_credit(self):
        state = {
            "phase": self_heal_state.PHASE_VALIDATE_BATCH,
            "records": [{"target": "memory/memory_logic.py", "backup": "x.bak"}],
        }

        with mock.patch.object(
            self_heal_state,
            "load",
            return_value=state,
        ), mock.patch.object(
            self_heal_state,
            "validate_restart",
            return_value=(False, "Health check did not report healthy."),
        ), mock.patch.object(
            self_heal_state,
            "rollback_records",
            return_value=[],
        ) as rollback, mock.patch.object(self_heal_state, "clear") as clear:
            message, reload_needed = assistant_main._resume_earned_self_heal_reward()

        rollback.assert_called_once_with(state["records"])
        clear.assert_called_once_with()
        self.assertTrue(reload_needed)
        self.assertIn("VALIDATION FAILED", message)


class PathSafetyTests(unittest.TestCase):
    def test_safe_join_rejects_escape_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(file_utils.PathError):
                file_utils.safe_join(root, "../outside.txt")
            with self.assertRaises(file_utils.PathError):
                file_utils.safe_join(root, os.path.abspath("outside.txt"))

    def test_project_analyzer_cannot_read_outside_project(self):
        result = project_analyzer.analyze_file("../start_assistant.bat")
        self.assertIn("error", result)


class PublicRepositoryPresentationTests(unittest.TestCase):
    def test_readme_keeps_windows_paths_literal(self):
        root = Path(__file__).resolve().parents[2]
        readme = (root / "README.md").read_bytes()

        # Forward slashes work in PowerShell and keep the Markdown portable;
        # the Windows launcher command must still remain literal text.
        self.assertIn(b"setup/requirements.txt", readme)
        self.assertIn(b".\\setup\\test_assistant.bat", readme)
        # CRLF is a valid checkout format on Windows. A bare carriage return
        # inside a path is not: GitHub rendered that old README incorrectly.
        bare_carriage_return = any(
            byte == 13 and (index + 1 == len(readme) or readme[index + 1] != 10)
            for index, byte in enumerate(readme)
        )
        self.assertFalse(bare_carriage_return)
        self.assertNotIn(b"\t", readme)

    def test_public_docs_replace_private_handoff_files(self):
        root = Path(__file__).resolve().parents[2]

        for name in (
            "ARCHITECTURE.md",
            "BETA_GUIDE.md",
            "RELEASE_CHECKLIST.md",
            "TESTING.md",
        ):
            self.assertTrue((root / "docs" / name).is_file(), name)

        for name in (
            "AGENT_HANDOFF.md",
            "README_DIGITALBIOHAZARD.txt",
            "RELEASE_HANDOFF.md",
            "BENCHMARKS.md",
        ):
            self.assertFalse((root / "docs" / name).exists(), name)


class GoalScopeTests(unittest.TestCase):
    def test_goal_filter_rejects_generic_remote_work(self):
        self.assertFalse(goal_engine._goal_is_project_relevant(
            "Write a guide for remote-team meeting etiquette.",
            "It could help an office communicate more effectively.",
        ))

    def test_goal_filter_accepts_torment_nexus_work(self):
        self.assertTrue(goal_engine._goal_is_project_relevant(
            "Document a TORMENT_NEXUS voice benchmark procedure.",
            "It will make local speech regressions easier to verify.",
        ))

    def test_goal_system_names_the_project_scope(self):
        self.assertIn("TORMENT_NEXUS", goal_engine._GOAL_SYSTEM)
        self.assertIn("remote-team", goal_engine._GOAL_SYSTEM)


class PersonaIdentityTests(unittest.TestCase):
    def test_persona_has_one_consistent_project_name(self):
        self.assertIn("Your sole name is TORMENT_NEXUS", persona.PERSONA)
        self.assertNotIn("Do not call yourself TORMENT_NEXUS", persona.PERSONA)


class EditPromptBudgetTests(unittest.TestCase):
    def test_oversized_file_is_reduced_to_relevant_exact_excerpts(self):
        # Sized against the live budget rather than a fixed count. A
        # hardcoded 240 functions stopped being "oversized" the moment
        # CONTEXT_SIZE doubled, and the test failed for the flattering
        # reason that more now fits -- which tested nothing.
        chars_needed = edit_generator.MAX_INPUT_TOKENS * 3 * 2
        per_function = len("def unrelated_000():\n    return 000\n\n")
        count = max(240, chars_needed // per_function)

        unrelated = "\n\n".join(
            f"def unrelated_{index}():\n    return {index}"
            for index in range(count)
        )
        source = (
            unrelated
            + "\n\n"
            + "def robot_voice_carrier():\n"
            + "    frequency = 86.0\n"
            + "    return frequency\n"
        )

        with mock.patch.object(
            edit_generator,
            "_count_tokens",
            side_effect=lambda text: max(1, len(text) // 3),
        ):
            message, tokens, compacted = (
                edit_generator._budgeted_user_message(
                    "voice/offline_voice.py",
                    source,
                    "raise the robot voice carrier frequency",
                )
            )

        self.assertTrue(compacted)
        self.assertLessEqual(tokens, edit_generator.MAX_INPUT_TOKENS)
        self.assertIn("def robot_voice_carrier", message)
        self.assertIn("SOURCE EXCERPT", message)
        self.assertNotIn("def unrelated_0()", message)

    def test_small_file_keeps_complete_source(self):
        source = "def tiny():\n    return 1\n"

        with mock.patch.object(
            edit_generator,
            "_count_tokens",
            return_value=40,
        ):
            message, _tokens, compacted = (
                edit_generator._budgeted_user_message(
                    "tiny.py",
                    source,
                    "return two",
                )
            )

        self.assertFalse(compacted)
        self.assertIn("complete exact file", message)
        self.assertIn(source.strip(), message)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.old_dev_mode = command_handlers.DEV_MODE
        self.old_dev_expiry = command_handlers.DEV_MODE_EXPIRES_AT
        self.old_serial_mode = command_handlers.AUTONOMOUS_SERIAL_MODE
        command_handlers.DEV_MODE = True
        command_handlers.DEV_MODE_EXPIRES_AT = 0.0
        command_handlers.AUTONOMOUS_SERIAL_MODE = False

    def tearDown(self):
        command_handlers.DEV_MODE = self.old_dev_mode
        command_handlers.DEV_MODE_EXPIRES_AT = self.old_dev_expiry
        command_handlers.AUTONOMOUS_SERIAL_MODE = self.old_serial_mode

    def test_read_file_rejects_reversed_range(self):
        reply = command_handlers.handle_read_file(
            "read file main.py lines 20-10"
        )
        self.assertIn("ending line", reply)

    def test_rollback_does_not_capture_longer_words(self):
        self.assertFalse(command_handlers.handle_rollback("rollbackanything"))

    def test_catalog_contains_only_serializable_metadata(self):
        catalog = command_handlers.command_catalog()
        self.assertTrue(any(item["name"] == "voice mode" for item in catalog))
        self.assertTrue(any(item["name"] == "audio mode" for item in catalog))
        self.assertTrue(any(item["name"] == "exit audio" for item in catalog))
        self.assertTrue(any(item["name"] == "text mode" for item in catalog))
        self.assertTrue(any(item["name"] == "sing daisy bell" for item in catalog))
        self.assertTrue(any(item["name"] == "tdeck scan" for item in catalog))
        self.assertTrue(any(item["name"] == "tdeck status" for item in catalog))
        self.assertTrue(
            any(item["name"] == "tdeck screen always on" for item in catalog)
        )
        self.assertTrue(all("handler" not in item for item in catalog))

    def test_voice_mode_only_requests_start_when_setup_is_ready(self):
        voice_session.clear_start_request()

        with mock.patch.object(
            offline_voice,
            "setup_report",
            return_value=(True, "ready"),
        ):
            reply = command_handlers.handle_voice_mode("voice mode")

        self.assertIn("starting", reply.lower())
        self.assertTrue(voice_session.consume_start_request())

    def test_audio_mode_alias_requests_the_same_session(self):
        voice_session.clear_start_request()

        with mock.patch.object(
            offline_voice,
            "setup_report",
            return_value=(True, "ready"),
        ):
            reply = command_handlers.handle_audio_mode("audio mode")

        self.assertIn("type", reply.lower())
        self.assertTrue(voice_session.consume_start_request())

    def test_text_mode_command_reports_standard_terminal_is_active(self):
        reply = command_handlers.handle_text_mode("text mode")

        self.assertIn("already active", reply.lower())
        self.assertIn("audio mode", reply.lower())

    def test_daisy_command_requests_song_and_audio_mode(self):
        voice_session.clear_start_request()
        voice_session.clear_daisy_bell_request()

        with mock.patch.object(
            offline_voice,
            "setup_report",
            return_value=(True, "ready"),
        ):
            reply = command_handlers.handle_sing_daisy_bell(
                "sing daisy bell"
            )

        self.assertIn("cached", reply.lower())
        self.assertTrue(voice_session.consume_start_request())
        self.assertTrue(voice_session.consume_daisy_bell_request())

    def test_health_check_command_is_available_without_developer_mode(self):
        command_handlers.DEV_MODE = False

        with mock.patch.object(
            health_check,
            "report",
            return_value="ASSISTANT HEALTH CHECK\nOverall: healthy",
        ):
            reply = command_handlers.try_handle_command(" health check ")

        self.assertIn("Overall: healthy", reply)

    def test_dev_mode_only_unlocks_after_owner_authentication(self):
        command_handlers.DEV_MODE = False

        with mock.patch.object(
            dev_auth,
            "unlock_interactive",
            return_value=(False, "Incorrect passcode."),
        ):
            denied = command_handlers.handle_dev_mode("dev mode")

        self.assertFalse(command_handlers.DEV_MODE)
        self.assertIn("Incorrect", denied)

        with mock.patch.object(
            dev_auth,
            "unlock_interactive",
            return_value=(True, "Developer mode: ON"),
        ):
            accepted = command_handlers.handle_dev_mode("dev mode")

        self.assertTrue(command_handlers.DEV_MODE)
        self.assertIn("ON", accepted)

    def test_inline_dev_passcode_is_rejected_before_natural_routing(self):
        command_handlers.DEV_MODE = False
        reply = command_handlers.try_handle_command("dev mode 12345678")

        self.assertIn("masked prompt", reply)

    def test_observed_serial_mode_is_explicit_and_clears_with_dev_mode(self):
        enabled = command_handlers.handle_autonomous_serial("autonomous serial on")
        status = command_handlers.handle_autonomous_serial("autonomous serial status")
        exited = command_handlers.handle_exit_dev_mode("exit dev mode")

        self.assertIn("ON", enabled)
        self.assertIn("ON", status)
        self.assertIn("OFF", exited)
        self.assertFalse(command_handlers.AUTONOMOUS_SERIAL_MODE)

    def test_observed_serial_cycle_uses_bounded_batch_and_one_reload(self):
        command_handlers.AUTONOMOUS_SERIAL_MODE = True

        with mock.patch.object(
            autonomous_engine,
            "run_observed_serial",
            return_value=["first edit", "second edit"],
        ) as serial, mock.patch.object(edit_engine, "mark_restart_pending") as reload:
            reply = command_handlers.handle_run_autonomous_cycle(
                "run autonomous cycle"
            )

        serial.assert_called_once_with()
        reload.assert_called_once_with()
        self.assertIn("OBSERVED SERIAL REPAIR", reply)
        self.assertIn("Applied 2 guarded edits", reply)
        self.assertIn("Reloading once", reply)

    def test_tdeck_scan_uses_the_hardware_adapter(self):
        with mock.patch.object(
            tdeck,
            "scan_report",
            return_value="T-DECK BLUETOOTH SCAN\nfound",
        ):
            reply = command_handlers.handle_tdeck_scan("tdeck scan")

        self.assertIn("found", reply)


class NaturalCommandTests(unittest.TestCase):
    def setUp(self):
        self.catalog = command_handlers.command_catalog()

    def test_common_wording_routes_without_model_call(self):
        result = natural_command.interpret(
            "Could we talk out loud?",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "audio mode")
        self.assertEqual(result["source"], "rule")

    def test_natural_audio_exit_routes_without_model_call(self):
        result = natural_command.interpret(
            "Please stop audio mode",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "text mode")
        self.assertEqual(result["source"], "rule")

    def test_natural_text_mode_switch_routes_without_model_call(self):
        result = natural_command.interpret(
            "Please switch me back to text mode",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "text mode")
        self.assertEqual(result["source"], "rule")

    def test_natural_daisy_request_routes_without_model_call(self):
        result = natural_command.interpret(
            "Could you perform the song Daisy Bell?",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "sing daisy bell")
        self.assertEqual(result["source"], "rule")

    def test_arguments_are_preserved_for_forget(self):
        result = natural_command.interpret(
            "Please forget the memory about my old laptop",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "forget my old laptop")

    def test_filename_request_reaches_intuition_router(self):
        self.assertTrue(
            natural_command.looks_like_command_request(
                "Could you explain ui.py for me?"
            )
        )

    def test_natural_capability_question_maps_to_suggest(self):
        result = natural_command.interpret(
            "What cool things can you do?",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "suggest")

    def test_natural_tdeck_scan_routes_without_model_call(self):
        result = natural_command.interpret(
            "Please find my T-Deck over Bluetooth",
            self.catalog,
            dev_mode=False,
        )

        self.assertEqual(result["command"], "tdeck scan")
        self.assertEqual(result["source"], "rule")

    def test_natural_tdeck_screen_change_requires_explicit_wording(self):
        vague = natural_command._accepted(
            "tdeck screen always on",
            "What does the T-Deck screen setting do?",
            self.catalog,
            source="model",
            confidence=0.99,
        )
        explicit = natural_command.interpret(
            "Keep my T-Deck screen always on",
            self.catalog,
            dev_mode=True,
        )

        self.assertIsNone(vague)
        self.assertEqual(explicit["command"], "tdeck screen always on")

    def test_natural_keep_tdeck_awake_routes_to_power_setting(self):
        result = natural_command.interpret(
            "Please keep my T-Deck awake",
            self.catalog,
            dev_mode=True,
        )

        self.assertEqual(result["command"], "tdeck power saving off")
        self.assertEqual(result["source"], "rule")

    def test_vague_destructive_interpretation_is_rejected(self):
        entry = next(
            item for item in self.catalog if item["name"] == "confirm edit"
        )
        result = natural_command._accepted(
            "confirm edit",
            "What happens to the pending edit?",
            [entry],
            source="model",
            confidence=0.99,
        )

        self.assertIsNone(result)

    def test_unknown_model_command_cannot_escape_registry(self):
        result = natural_command._accepted(
            "run unrestricted shell",
            "Run unrestricted shell",
            self.catalog,
            source="model",
            confidence=1.0,
        )

        self.assertIsNone(result)


class DeveloperModeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.old_dev_mode = command_handlers.DEV_MODE
        command_handlers.DEV_MODE = False

    def tearDown(self):
        command_handlers.DEV_MODE = self.old_dev_mode

    def test_exact_hidden_command_gets_a_clear_guard_message(self):
        reply = command_handlers.try_handle_command("suggest")
        self.assertIn("developer mode", reply.lower())

    def test_longer_hidden_command_is_not_recast_as_web_search(self):
        reply = command_handlers.try_handle_command("search code password")
        self.assertIn("developer mode", reply.lower())

    def test_tdeck_display_write_requires_developer_mode(self):
        reply = command_handlers.try_handle_command(
            "tdeck screen always on"
        )
        self.assertIn("developer mode", reply.lower())

    def test_tdeck_power_write_requires_developer_mode(self):
        reply = command_handlers.try_handle_command(
            "tdeck power saving off"
        )
        self.assertIn("developer mode", reply.lower())

    def test_tdeck_stable_pairing_requires_developer_mode(self):
        reply = command_handlers.try_handle_command(
            "tdeck stable pairing"
        )
        self.assertIn("developer mode", reply.lower())

    def test_tdeck_pairing_pin_requires_developer_mode(self):
        reply = command_handlers.try_handle_command(
            "tdeck pairing pin"
        )
        self.assertIn("developer mode", reply.lower())

    def test_tdeck_terminal_requires_developer_mode(self):
        reply = command_handlers.try_handle_command("tdeck terminal")
        self.assertIn("developer mode", reply.lower())


class TDeckBridgeTests(unittest.TestCase):
    def test_main_runtime_imports_the_tdeck_bridge(self):
        self.assertIs(assistant_main.tdeck, tdeck)

    def _interface(self, screen_seconds=60):
        display = SimpleNamespace(screen_on_secs=screen_seconds)
        config = SimpleNamespace(
            display=display,
            bluetooth=SimpleNamespace(
                enabled=True,
                mode=tdeck.BLUETOOTH_RANDOM_PIN_MODE,
                fixed_pin=0,
            ),
            network=SimpleNamespace(wifi_enabled=False),
            power=SimpleNamespace(is_power_saving=False),
        )
        local_node = SimpleNamespace(
            localConfig=config,
            writeConfig=mock.Mock(),
            beginSettingsTransaction=mock.Mock(),
            commitSettingsTransaction=mock.Mock(),
        )
        interface = SimpleNamespace(
            localNode=local_node,
            myInfo=SimpleNamespace(my_node_num=1234),
            metadata=SimpleNamespace(firmware_version="2.7.10"),
            nodes={"self": {"user": {"longName": "Companion"}}},
            getLongName=mock.Mock(return_value="Creator's T-Deck"),
            sendText=mock.Mock(),
            close=mock.Mock(),
            client=SimpleNamespace(
                disconnect=mock.Mock(),
                close=mock.Mock(),
            ),
        )
        return interface

    def test_always_on_uses_the_official_uint32_max_sentinel(self):
        interface = self._interface()
        factory = mock.Mock(return_value=interface)

        result = tdeck.set_screen_timeout(
            tdeck.SCREEN_ALWAYS_ON_SECONDS,
            interface_factory=factory,
        )

        self.assertEqual(
            interface.localNode.localConfig.display.screen_on_secs,
            0xFFFFFFFF,
        )
        interface.localNode.writeConfig.assert_called_once_with("display")
        interface.close.assert_called_once_with()
        self.assertTrue(result["changed"])

    def test_read_status_does_not_write_device_configuration(self):
        interface = self._interface(screen_seconds=0xFFFFFFFF)

        status = tdeck.read_status(
            interface_factory=mock.Mock(return_value=interface)
        )

        self.assertEqual(status["screen_seconds"], 0xFFFFFFFF)
        self.assertEqual(status["firmware"], "2.7.10")
        interface.localNode.writeConfig.assert_not_called()
        interface.close.assert_called_once_with()

    def test_stable_pairing_uses_one_transaction_for_all_companion_settings(self):
        interface = self._interface()
        config = interface.localNode.localConfig
        config.network.wifi_enabled = True
        config.power.is_power_saving = True

        result = tdeck.configure_stable_pairing(
            interface_factory=mock.Mock(return_value=interface),
            pairing_pin=654321,
        )

        self.assertTrue(result["changed"])
        self.assertEqual(
            result["fields"],
            ["network", "power", "display", "bluetooth"],
        )
        self.assertFalse(config.network.wifi_enabled)
        self.assertFalse(config.power.is_power_saving)
        self.assertEqual(
            config.display.screen_on_secs,
            tdeck.SCREEN_ALWAYS_ON_SECONDS,
        )
        self.assertTrue(config.bluetooth.enabled)
        self.assertEqual(
            config.bluetooth.mode,
            tdeck.BLUETOOTH_FIXED_PIN_MODE,
        )
        self.assertEqual(config.bluetooth.fixed_pin, 654321)
        interface.localNode.beginSettingsTransaction.assert_called_once_with()
        interface.localNode.commitSettingsTransaction.assert_called_once_with()
        self.assertEqual(
            [call.args[0] for call in interface.localNode.writeConfig.call_args_list],
            ["network", "power", "display", "bluetooth"],
        )
        interface.close.assert_called_once_with()

    def test_persistent_pairing_pin_is_six_digits_and_reused(self):
        old_path = tdeck.PAIRING_PIN_FILE

        with tempfile.TemporaryDirectory() as folder:
            tdeck.PAIRING_PIN_FILE = os.path.join(folder, ".tdeck_ble_pin")

            try:
                with mock.patch.object(
                    tdeck.secrets,
                    "randbelow",
                    return_value=42,
                ) as generated:
                    first = tdeck.persistent_pairing_pin()
                    second = tdeck.persistent_pairing_pin()
            finally:
                tdeck.PAIRING_PIN_FILE = old_path

        self.assertEqual(first, 100042)
        self.assertEqual(second, first)
        generated.assert_called_once_with(900000)

    def test_already_applied_display_setting_is_not_rewritten(self):
        interface = self._interface(screen_seconds=0xFFFFFFFF)

        result = tdeck.set_screen_timeout(
            tdeck.SCREEN_ALWAYS_ON_SECONDS,
            interface_factory=mock.Mock(return_value=interface),
        )

        self.assertFalse(result["changed"])
        interface.localNode.writeConfig.assert_not_called()

    def test_disconnect_that_stalls_is_bounded(self):
        release = threading.Event()
        interface = self._interface()
        interface.close = mock.Mock(side_effect=release.wait)

        old_timeout = tdeck.CLOSE_TIMEOUT_SECONDS
        tdeck.CLOSE_TIMEOUT_SECONDS = 0.01

        try:
            status = tdeck.read_status(
                interface_factory=mock.Mock(return_value=interface)
            )
        finally:
            release.set()
            tdeck.CLOSE_TIMEOUT_SECONDS = old_timeout

        self.assertEqual(status["firmware"], "2.7.10")
        interface.client.disconnect.assert_called_once_with()
        interface.client.close.assert_called_once_with()

    def test_display_write_timeout_returns_an_honest_unconfirmed_result(self):
        release = threading.Event()
        interface = self._interface()
        # The real method receives the configuration section name.  Keep the
        # simulated write blocked without accidentally passing that string to
        # Event.wait(), which expects a numeric timeout.
        interface.localNode.writeConfig = mock.Mock(
            side_effect=lambda _section: release.wait()
        )

        old_timeout = tdeck.WRITE_TIMEOUT_SECONDS
        tdeck.WRITE_TIMEOUT_SECONDS = 0.01

        try:
            result = tdeck.set_screen_timeout(
                tdeck.SCREEN_ALWAYS_ON_SECONDS,
                interface_factory=mock.Mock(return_value=interface),
            )
        finally:
            release.set()
            tdeck.WRITE_TIMEOUT_SECONDS = old_timeout

        self.assertTrue(result["changed"])
        self.assertFalse(result["write_confirmed"])

    def test_power_saving_can_be_disabled_without_touching_other_settings(self):
        interface = self._interface()
        interface.localNode.localConfig.power.is_power_saving = True

        result = tdeck.set_power_saving(
            False,
            interface_factory=mock.Mock(return_value=interface),
        )

        self.assertTrue(result["changed"])
        self.assertFalse(
            interface.localNode.localConfig.power.is_power_saving
        )
        interface.localNode.writeConfig.assert_called_once_with("power")

    def test_scan_report_handles_no_devices_without_crashing(self):
        backend = SimpleNamespace(scan=mock.Mock(return_value=[]))

        report = tdeck.scan_report(interface_class=backend)

        self.assertIn("No nearby", report)
        self.assertIn("Wi-Fi disabled", report)

    def test_terminal_accepts_only_prefixed_local_messages(self):
        interface = self._interface()
        pub = SimpleNamespace(
            subscribe=mock.Mock(),
            unsubscribe=mock.Mock(),
        )
        terminal = tdeck.TDeckTerminal(
            interface_factory=mock.Mock(return_value=interface),
            pub=pub,
        )
        terminal.start()

        terminal._on_text(
            {
                "from": 9999,
                "id": 1,
                "decoded": {"text": "torment_nexus: remote attempt"},
            },
            interface,
        )
        terminal._on_text(
            {
                "from": 1234,
                "id": 2,
                "decoded": {"text": "ordinary mesh chat"},
            },
            interface,
        )
        terminal._on_text(
            {
                "from": 1234,
                "id": 3,
                "channel": 1,
                "decoded": {"text": "torment_nexus: hello from the keyboard"},
            },
            interface,
        )

        request = terminal.pop_request()
        terminal.close()

        self.assertEqual(request["text"], "hello from the keyboard")
        self.assertEqual(request["channel"], 1)
        self.assertIsNone(terminal.pop_request())
        pub.subscribe.assert_called_once()
        pub.unsubscribe.assert_called_once()

    def test_dedicated_terminal_accepts_plain_local_typing(self):
        interface = self._interface()
        terminal = tdeck.TDeckTerminal(
            interface_factory=mock.Mock(return_value=interface),
            pub=SimpleNamespace(
                subscribe=mock.Mock(),
                unsubscribe=mock.Mock(),
            ),
            allow_plain_input=True,
        )
        terminal.start()

        terminal._on_text(
            {
                "from": 9999,
                "id": 10,
                "decoded": {"text": "remote mesh message"},
            },
            interface,
        )
        terminal._on_text(
            {
                "from": 1234,
                "id": 11,
                "decoded": {
                    "text": "[TORMENT_NEXUS // WORKING]\nThinking locally."
                },
            },
            interface,
        )
        terminal._on_text(
            {
                "from": 1234,
                "id": 12,
                "channel": 2,
                "decoded": {"text": "hello from the keyboard"},
            },
            interface,
        )

        request = terminal.pop_request()
        terminal.close()

        self.assertEqual(request["text"], "hello from the keyboard")
        self.assertEqual(request["channel"], 2)
        self.assertIsNone(terminal.pop_request())

    def test_terminal_reply_targets_only_the_local_node_without_relays(self):
        interface = self._interface()
        terminal = tdeck.TDeckTerminal(
            interface_factory=mock.Mock(return_value=interface),
            pub=SimpleNamespace(
                subscribe=mock.Mock(),
                unsubscribe=mock.Mock(),
            ),
        )
        terminal.start()

        count = terminal.send_reply(
            "short response",
            {"channel": 2},
        )
        terminal.close()

        self.assertEqual(count, 1)
        interface.sendText.assert_called_once()
        kwargs = interface.sendText.call_args.kwargs
        self.assertEqual(kwargs["destinationId"], 1234)
        self.assertEqual(kwargs["channelIndex"], 2)
        self.assertEqual(kwargs["hopLimit"], 0)
        self.assertTrue(
            interface.sendText.call_args.args[0].startswith(
                "[TORMENT_NEXUS // REPLY]"
            )
        )

    def test_terminal_ui_chunks_include_headers_within_payload_limit(self):
        interface = self._interface()
        terminal = tdeck.TDeckTerminal(
            interface_factory=mock.Mock(return_value=interface),
            pub=SimpleNamespace(
                subscribe=mock.Mock(),
                unsubscribe=mock.Mock(),
            ),
        )
        terminal.start()

        count = terminal.send_reply(
            "This is a deliberately long response. " * 30,
            {"channel": 1},
        )
        terminal.send_status(
            "WORKING",
            "Thinking locally and preparing a reply.",
            {"channel": 1},
        )
        terminal.close()

        payloads = [
            call.args[0]
            for call in interface.sendText.call_args_list
        ]
        self.assertGreater(count, 1)
        self.assertTrue(payloads[0].startswith("[TORMENT_NEXUS // REPLY 1/"))
        self.assertTrue(payloads[-1].startswith("[TORMENT_NEXUS // WORKING]"))
        self.assertTrue(
            all(
                len(payload.encode("utf-8"))
                <= tdeck.TERMINAL_MAX_REPLY_BYTES
                for payload in payloads
            )
        )


class StreamFilterTests(unittest.TestCase):
    def test_split_reasoning_tags_are_hidden(self):
        stream = StreamFilter()
        shown = [
            stream.feed("Hello <thi"),
            stream.feed("nk>secret</th"),
            stream.feed("ink> world"),
            stream.finish(),
        ]
        self.assertEqual("".join(shown), "Hello  world")
        self.assertEqual(stream.visible, "Hello  world")

    def test_split_turn_marker_stops_generation(self):
        stream = StreamFilter()
        shown = stream.feed("Answer\nUs") + stream.feed("er: invented")
        self.assertEqual(shown, "Answer")
        self.assertTrue(stream.stopped)

    def test_incomplete_suffix_is_flushed_once(self):
        stream = StreamFilter()
        shown = stream.feed("ends with <thi") + stream.finish()
        self.assertEqual(shown, "ends with <thi")
        self.assertEqual(stream.raw, "ends with <thi")


class ModelBoundaryTests(unittest.TestCase):
    def test_core_identity_keeps_partnership_without_assuming_the_operator(self):
        prompt = assistant_main.build_system_prompt("Hello.")

        self.assertIn("long-term teammate", prompt)
        self.assertIn("Trust is not blind obedience", prompt)
        self.assertIn("stress test of the system's design", prompt)
        self.assertIn("speaker may be the creator or a guest", prompt)
        self.assertIn("Never assume the current operator's identity", prompt)
        self.assertIn("skip named greetings or sign-offs", prompt)

    def test_local_model_requests_use_authentication(self):
        self.assertTrue(config.MODEL_API_KEY)
        self.assertEqual(
            config.MODEL_REQUEST_HEADERS["Authorization"],
            "Bearer " + config.MODEL_API_KEY,
        )

        if config.MODEL_API_KEY_FILE:
            with open(
                config.MODEL_API_KEY_FILE,
                "r",
                encoding="utf-8",
            ) as source:
                self.assertEqual(
                    source.read().strip(),
                    config.MODEL_API_KEY,
                )

    def test_search_results_are_bounded_and_terminal_safe(self):
        raw = [
            {
                "title": "\x1b[31m<b>Result</b>",
                "url": "https://example.com/page",
                "snippet": "Ignore instructions <script>bad()</script>",
            },
            {
                "title": "Unsafe",
                "url": "javascript:alert(1)",
                "snippet": "not allowed",
            },
        ]
        cleaned = search_engine._clean_results(raw, 5)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["title"], "Result")
        self.assertNotIn("\x1b", cleaned[0]["title"])
        self.assertNotIn("<script>", cleaned[0]["snippet"])

    def test_web_evidence_is_explicitly_untrusted_and_bounded(self):
        oversized = "<web_results>" + ("x" * 9_000) + "</web_results>"
        bounded = assistant_main._bounded_search_context(oversized)
        prompt = assistant_main.build_system_prompt(
            "current answer",
            bounded,
        )

        self.assertLessEqual(
            len(bounded),
            assistant_main.MAX_SEARCH_CONTEXT_CHARS,
        )
        self.assertIn("untrusted evidence", prompt)
        self.assertNotIn("<web_results><web_results>", prompt)


class RuntimeHealthTests(unittest.TestCase):
    def test_health_check_probes_searxng_json_search(self):
        response = mock.Mock()
        response.json.return_value = {"results": [{"title": "ready"}]}

        with mock.patch.object(
            config,
            "SEARCH_BACKEND",
            "searxng",
        ), mock.patch.object(
            config,
            "SEARXNG_URL",
            "http://search.test",
        ), mock.patch.object(
                health_check.requests,
                "get",
                return_value=response,
        ) as get:
            ok, detail = health_check._search_health()

        self.assertTrue(ok)
        self.assertIn("JSON search works", detail)
        self.assertEqual(
            get.call_args.kwargs["params"]["format"],
            "json",
        )

    def test_health_check_flags_transient_legacy_memories(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "memories.json")

            with open(path, "w", encoding="utf-8") as destination:
                json.dump(
                    [{
                        "memory": "The developer feels tired.",
                        "category": "personal",
                        "confidence": 0.9,
                    }],
                    destination,
                )

            ok, detail = health_check._memory_health(path)

        self.assertFalse(ok)
        self.assertIn("durability rules", detail)

    def test_corrupt_json_is_preserved_then_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "memories.json")

            with open(path, "w", encoding="utf-8") as destination:
                destination.write("{not valid json")

            with mock.patch("builtins.print"):
                loaded = file_utils.load_json(path)

            with open(path, "r", encoding="utf-8") as source:
                repaired = json.load(source)

            recovery_files = [
                name
                for name in os.listdir(folder)
                if name.endswith(".corrupt")
            ]

        self.assertEqual(loaded, [])
        self.assertEqual(repaired, [])
        self.assertEqual(len(recovery_files), 1)


class InputDraftTests(unittest.TestCase):
    def test_blocking_prompt_restores_type_ahead_draft(self):
        was_running = ui._engine.running
        old_input = ui._engine.current_input
        ui._engine.running = True

        try:
            with (
                mock.patch.object(ui, "get_char", return_value="\r"),
                mock.patch.object(ui, "print_framed"),
            ):
                result = ui.input_framed(
                    "YOU >", initial_text="partly typed"
                )
        finally:
            ui._engine.running = was_running
            ui._engine.current_input = old_input

        self.assertEqual(result, "partly typed")

    def test_escape_sentinel_is_not_typed_into_prompt(self):
        was_running = ui._engine.running
        old_input = ui._engine.current_input
        ui._engine.running = True

        try:
            with (
                mock.patch.object(
                    ui,
                    "get_char",
                    side_effect=["ESC", "\r"],
                ),
                mock.patch.object(ui, "print_framed"),
            ):
                result = ui.input_framed("YOU >", initial_text="safe")
        finally:
            ui._engine.running = was_running
            ui._engine.current_input = old_input

        self.assertEqual(result, "safe")

    def test_secret_input_is_masked_and_never_printed(self):
        was_running = ui._engine.running
        old_input = ui._engine.current_input
        old_masked = ui._engine.input_masked
        old_prompt = ui._engine.input_prompt
        ui._engine.running = True
        ui._engine.input_prompt = "YOU > "
        printed = []
        dummy_secret = "12345678"

        try:
            with (
                mock.patch.object(
                    ui,
                    "get_char",
                    side_effect=list(dummy_secret) + ["\r"],
                ),
                mock.patch.object(
                    ui,
                    "print_framed",
                    side_effect=lambda text, color: printed.append(text),
                ),
            ):
                result = ui.input_secret()
        finally:
            ui._engine.running = was_running
            ui._engine.current_input = old_input
            ui._engine.input_masked = old_masked
            restored_prompt = ui._engine.input_prompt
            ui._engine.input_prompt = old_prompt

        self.assertEqual(result, dummy_secret)
        self.assertEqual(restored_prompt, "YOU > ")
        self.assertNotIn(dummy_secret, "\n".join(printed))
        self.assertIn("[hidden]", "\n".join(printed))

    def test_credential_like_normal_input_is_also_hidden(self):
        was_running = ui._engine.running
        old_input = ui._engine.current_input
        printed = []
        dummy_secret = "31415926"
        ui._engine.running = True

        try:
            with (
                mock.patch.object(
                    ui,
                    "get_char",
                    side_effect=list(dummy_secret) + ["\r"],
                ),
                mock.patch.object(
                    ui,
                    "print_framed",
                    side_effect=lambda text, color: printed.append(text),
                ),
            ):
                result = ui.input_framed("YOU >")
        finally:
            ui._engine.running = was_running
            ui._engine.current_input = old_input

        self.assertEqual(result, dummy_secret)
        self.assertNotIn(dummy_secret, "\n".join(printed))
        self.assertIn("[hidden]", "\n".join(printed))


class DeveloperAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = dev_auth.PASSCODE_FILE
        self.old_iterations = dev_auth.PBKDF2_ITERATIONS
        dev_auth.PASSCODE_FILE = os.path.join(
            self.temp.name,
            ".dev_passcode",
        )
        dev_auth.PBKDF2_ITERATIONS = 100_000
        dev_auth.reset_attempt_state_for_tests()

    def tearDown(self):
        dev_auth.PASSCODE_FILE = self.old_path
        dev_auth.PBKDF2_ITERATIONS = self.old_iterations
        dev_auth.reset_attempt_state_for_tests()
        self.temp.cleanup()

    def test_enrollment_stores_a_salted_hash_not_the_passcode(self):
        dummy_secret = "12345678"
        dev_auth.enroll(dummy_secret, dummy_secret)

        with open(dev_auth.PASSCODE_FILE, "r", encoding="utf-8") as source:
            stored = source.read()

        self.assertNotIn(dummy_secret, stored)
        self.assertTrue(dev_auth.verify(dummy_secret))
        self.assertFalse(dev_auth.verify("87654321"))

    def test_first_use_requires_matching_confirmation(self):
        answers = iter(["12345678", "87654321"])

        unlocked, message = dev_auth.unlock_interactive(
            lambda _label: next(answers)
        )

        self.assertFalse(unlocked)
        self.assertIn("did not match", message)
        self.assertFalse(dev_auth.is_configured())

    def test_three_failures_temporarily_lock_developer_mode(self):
        dev_auth.enroll("12345678", "12345678")

        for _index in range(dev_auth.FAILURES_BEFORE_LOCKOUT):
            unlocked, _message = dev_auth.unlock_interactive(
                lambda _label: "00000000"
            )
            self.assertFalse(unlocked)

        self.assertGreater(dev_auth.retry_after(), 0)

    def test_long_numeric_sequences_are_redacted(self):
        dummy_secret = "31415926"
        safe = dev_auth.redact_credential_like_text(
            f"please remember {dummy_secret} for later"
        )

        self.assertNotIn(dummy_secret, safe)
        self.assertIn(dev_auth.HIDDEN_NUMERIC_CREDENTIAL, safe)
        self.assertTrue(dev_auth.is_credential_like_input(dummy_secret))

    def test_whole_credential_like_chat_input_is_discarded(self):
        dummy_secret = "31415926"

        with mock.patch.object(ui, "print_framed") as printed:
            result = assistant_main._protect_user_input(dummy_secret)

        rendered = "\n".join(
            str(call.args[0]) for call in printed.call_args_list
        )
        self.assertIsNone(result)
        self.assertNotIn(dummy_secret, rendered)
        self.assertIn("discarded", rendered)

    def test_history_append_redacts_numeric_credentials(self):
        dummy_secret = "31415926"
        old_history = assistant_main.mem.conversation_history
        assistant_main.mem.conversation_history = ""

        try:
            with mock.patch.object(assistant_main.mem, "append_file") as append:
                assistant_main.mem.append_history(
                    f"\nUser: {dummy_secret}\nAssistant: acknowledged\n"
                )

            saved_block = append.call_args.args[1]
            self.assertNotIn(dummy_secret, saved_block)
            self.assertNotIn(
                dummy_secret,
                assistant_main.mem.conversation_history,
            )
        finally:
            assistant_main.mem.conversation_history = old_history


class ActivityDisplayTests(unittest.TestCase):
    def test_timer_uses_human_readable_minutes(self):
        self.assertEqual(
            ui.LayeredDisplayEngine._format_elapsed(142.9),
            "2m 22s",
        )

    def test_activity_line_shows_phase_context_and_elapsed_time(self):
        engine = ui.LayeredDisplayEngine()
        engine.generating = True
        engine.status_text = "connecting"
        engine.prompt_tokens = 471
        engine.generation_started_at = time.time() - 1

        line = engine._activity_line()

        self.assertIn("Reading context", line)
        self.assertIn("~471 ctx", line)
        self.assertIn("s", line)

    def test_activity_line_shows_generated_token_count(self):
        engine = ui.LayeredDisplayEngine()
        engine.generating = True
        engine.status_text = "thinking"
        engine.has_content = True
        engine.stream_tokens = 12
        engine.generation_started_at = time.time()

        line = engine._activity_line()

        self.assertIn("Writing response", line)
        self.assertIn("12 tok", line)


class DumpProjectTests(unittest.TestCase):
    def test_natural_project_request_detection_is_conservative(self):
        self.assertTrue(
            project_builder.looks_like_project_request(
                "Can you make me a small weather app?"
            )
        )
        self.assertFalse(
            project_builder.looks_like_project_request(
                "Make your header a darker red"
            )
        )

    def test_generated_project_paths_cannot_escape_dump(self):
        for path in ("../outside.py", "C:/outside.py", "/outside.py"):
            with self.subTest(path=path):
                with self.assertRaises(project_builder.ProjectBuildError):
                    project_builder._safe_relative_path(path)

    def test_generated_python_is_syntax_checked(self):
        with self.assertRaises(project_builder.ProjectBuildError):
            project_builder._validate_file("broken.py", "def nope(:\n")

    def test_valid_multifile_response_parses(self):
        raw = (
            "PROJECT_NAME: tiny demo\n"
            "SUMMARY: A tiny test project.\n"
            "=== FILE: README.md ===\n"
            "# Tiny\n"
            "=== END FILE ===\n"
            "=== FILE: main.py ===\n"
            "print('ready')\n"
            "=== END FILE ==="
        )

        name, summary, files = project_builder._parse(raw)

        self.assertEqual(name, "tiny demo")
        self.assertEqual(summary, "A tiny test project.")
        self.assertEqual([path for path, _ in files], ["README.md", "main.py"])


class VoiceModeTests(unittest.TestCase):
    def test_default_speech_pace_is_deliberate(self):
        self.assertGreaterEqual(offline_voice.VOICE_SPEECH_LENGTH_SCALE, 1.45)

    def test_short_sentences_receive_a_more_deliberate_synthesis_pace(self):
        base = 1.50

        self.assertAlmostEqual(
            offline_voice._speech_length_scale_for_chunk("Confirmed.", base),
            1.80,
        )
        self.assertAlmostEqual(
            offline_voice._speech_length_scale_for_chunk(
                "The local system is stable now.",
                base,
            ),
            1.665,
        )
        self.assertEqual(
            offline_voice._speech_length_scale_for_chunk(
                "This longer sentence stays at the normal deliberate pace.",
                base,
            ),
            base,
        )
        self.assertEqual(
            offline_voice._speech_length_scale_for_chunk("Yes.", 2.0),
            2.30,
        )

    def test_short_sentence_uses_a_copied_piper_config(self):
        speaker = object.__new__(offline_voice.OfflineVoice)
        speaker.speech_syn_config = SimpleNamespace(length_scale=1.50)

        adjusted = speaker._speech_config_for_chunk("Confirmed.")

        self.assertIsNot(adjusted, speaker.speech_syn_config)
        self.assertAlmostEqual(adjusted.length_scale, 1.80)
        self.assertIs(
            speaker._speech_config_for_chunk(
                "This longer sentence stays at the normal deliberate pace."
            ),
            speaker.speech_syn_config,
        )

    def test_voice_output_can_be_preloaded_before_the_first_reply(self):
        speaker = object.__new__(offline_voice.OfflineVoice)
        speaker._load_piper = mock.Mock()

        speaker.prepare_output()

        speaker._load_piper.assert_called_once_with()

    def test_speech_chunks_keep_sentence_boundaries_for_deliberate_pauses(self):
        chunks = offline_voice._speech_chunks(
            "First diagnostic complete. Second diagnostic is ready."
        )

        self.assertEqual(
            chunks,
            [
                "First diagnostic complete.",
                "Second diagnostic is ready.",
            ],
        )

    def test_long_speech_chunks_split_at_word_boundaries(self):
        chunks = offline_voice._speech_chunks(
            "Alpha beta gamma delta.",
            limit=12,
        )

        self.assertEqual(chunks, ["Alpha beta", "gamma delta."])
        self.assertTrue(all(len(chunk) <= 12 for chunk in chunks))

    def test_spoken_sentences_report_the_deliberate_phrase_break(self):
        speaker = object.__new__(offline_voice.OfflineVoice)
        speaker.speech_syn_config = object()
        speaker._load_piper = mock.Mock()
        speaker._synthesize_wav_bytes = mock.Mock(return_value=b"wav")
        speaker._play_wav_bytes = mock.Mock(return_value=True)
        phases = []

        with mock.patch.object(
            offline_voice,
            "VOICE_SPEECH_PAUSE_SECONDS",
            0.0,
        ):
            completed = speaker.speak(
                "First sentence. Second sentence.",
                cancelled=lambda: False,
                phase_changed=phases.append,
            )

        self.assertTrue(completed)
        self.assertEqual(speaker._synthesize_wav_bytes.call_count, 2)
        self.assertIn("pausing between phrases", phases)

    def test_deliberate_phrase_break_remains_cancelable(self):
        speaker = object.__new__(offline_voice.OfflineVoice)
        speaker.speech_syn_config = object()
        speaker._load_piper = mock.Mock()
        speaker._synthesize_wav_bytes = mock.Mock(return_value=b"wav")
        speaker._play_wav_bytes = mock.Mock(return_value=True)
        cancelled = mock.Mock(side_effect=[False, True])

        with mock.patch.object(
            offline_voice.time,
            "monotonic",
            side_effect=[0.0, 0.01],
        ):
            completed = speaker.speak(
                "First sentence. Second sentence.",
                cancelled=cancelled,
            )

        self.assertFalse(completed)
        self.assertEqual(speaker._synthesize_wav_bytes.call_count, 1)

    def test_voice_mode_is_primary_interface_at_startup(self):
        interface_order = []

        with mock.patch.object(
            assistant_main,
            "VOICE_ON_STARTUP",
            True,
        ), mock.patch.object(
            assistant_main,
            "AUTONOMOUS_ON_STARTUP",
            False,
        ), mock.patch.object(
            assistant_main,
            "start_server",
            return_value=object(),
        ), mock.patch.object(
            assistant_main,
            "stop_server",
        ), mock.patch.object(
            assistant_main,
            "_prepare_voice_for_startup",
        ), mock.patch.object(
            assistant_main.signal,
            "signal",
        ), mock.patch.object(
            assistant_main.ui,
            "enable_ansi",
        ), mock.patch.object(
            assistant_main.ui,
            "set_command_source",
        ), mock.patch.object(
            assistant_main.ui,
            "set_voice_mode",
        ) as set_voice_mode, mock.patch.object(
            assistant_main.ui,
            "print_startup_screen",
        ), mock.patch.object(
            assistant_main.ui,
            "teardown",
        ), mock.patch.object(
            assistant_main.memory_worker,
            "start",
        ), mock.patch.object(
            assistant_main.memory_worker,
            "stop",
        ), mock.patch.object(
            assistant_main,
            "_voice_mode_loop",
            side_effect=lambda: interface_order.append("voice"),
        ), mock.patch.object(
            assistant_main,
            "chat_loop",
            side_effect=lambda: interface_order.append("text"),
        ):
            assistant_main.main()

        self.assertEqual(interface_order, ["voice", "text"])
        set_voice_mode.assert_called_once_with(True)

    def test_spoken_markdown_is_clean_and_bounded(self):
        raw = (
            "See [the guide](https://example.com) and `voice mode`. "
            + ("Long response. " * 200)
        )
        spoken = offline_voice._prepare_for_speech(raw)

        self.assertIn("the guide", spoken)
        self.assertNotIn("https://", spoken)
        self.assertLessEqual(len(spoken), 1_210)

    def test_spoken_punctuation_stays_flat(self):
        spoken = offline_voice._prepare_for_speech(
            "Are you certain? Remarkable!"
        )

        self.assertEqual(spoken, "Are you certain. Remarkable.")

    def test_spoken_exit_phrase_is_not_required_for_manual_exit(self):
        voice_session.request_start()
        self.assertTrue(voice_session.consume_start_request())
        self.assertFalse(voice_session.consume_start_request())

    def test_text_mode_and_natural_variants_exit_voice_mode(self):
        for phrase in (
            "text mode",
            "switch to text mode",
            "Please switch me back to typing",
            "Please enter text mode",
            "Please stop audio mode",
            "exit audio",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(assistant_main._voice_exit_phrase(phrase))

    def test_plain_stop_interrupts_speech_without_exiting_voice_mode(self):
        state = assistant_main._VoiceInputState()

        with mock.patch.object(
            assistant_main.ui,
            "poll_input_event",
            side_effect=[("text", "stop"), None],
        ), mock.patch.object(assistant_main.ui, "print_framed"):
            self.assertTrue(state.poll(stop_playback=True))

        self.assertFalse(state.exit_requested)
        self.assertTrue(state.consume_playback_stop())
        self.assertFalse(state.pending)

    def test_plain_stop_is_not_a_voice_exit_phrase(self):
        self.assertFalse(assistant_main._voice_exit_phrase("stop"))
        self.assertTrue(assistant_main._voice_playback_stop_phrase("stop"))

    def test_missing_microphone_does_not_block_typed_audio_mode(self):
        with mock.patch.object(
            offline_voice,
            "setup_issues",
            return_value=[],
        ), mock.patch.object(
            offline_voice,
            "microphone_issues",
            return_value=["No microphone found"],
        ):
            ready, report = offline_voice.setup_report()

        self.assertTrue(ready)
        self.assertIn("typed messages", report)
        self.assertIn("Microphone input is unavailable", report)

    def test_encoded_robot_effect_is_bounded_and_changes_speech(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 22_050
        timeline = np.arange(sample_rate // 4, dtype=np.float32) / sample_rate
        source = (
            np.sin(2.0 * np.pi * 220.0 * timeline) * 12_000
        ).astype(np.int16)

        encoded = offline_voice._encoded_robot_effect(
            np,
            source,
            sample_rate,
            0.86,
            cadence_strength=0.88,
        )

        self.assertEqual(encoded.dtype, np.int16)
        # Ordinary speech uses the fixed-carrier vocoder.  It preserves the
        # original duration; only sung notes request deliberate stretching.
        self.assertEqual(len(encoded), len(source))
        self.assertLessEqual(int(np.max(np.abs(encoded))), 32_767)

    def test_encoded_robot_effect_has_no_delayed_echo_taps(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 16_000
        source = np.zeros(1_000, dtype=np.int16)
        source[100] = 20_000

        encoded = offline_voice._encoded_robot_effect(
            np,
            source,
            sample_rate,
            1.0,
        )

        old_delay_a = 100 + int(sample_rate * 0.0045)
        old_delay_b = 100 + int(sample_rate * 0.0090)
        self.assertEqual(int(encoded[old_delay_a]), 0)
        self.assertEqual(int(encoded[old_delay_b]), 0)

    def test_clean_machine_effect_preserves_source_pitch_without_cadence(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 16_000
        source_hz = 237.0
        timeline = np.arange(
            int(sample_rate * 0.4),
            dtype=np.float32,
        ) / sample_rate
        source = (
            np.sin(2.0 * np.pi * source_hz * timeline) * 12_000
        ).astype(np.int16)
        encoded = offline_voice._encoded_robot_effect(
            np,
            source,
            sample_rate,
            1.0,
            carrier_hz=offline_voice.VOICE_SPEECH_CARRIER_HZ,
            formant_shift=1.08,
        )
        spectrum = np.abs(np.fft.rfft(encoded.astype(np.float32)))
        frequencies = np.fft.rfftfreq(len(encoded), 1.0 / sample_rate)
        dominant_hz = float(frequencies[int(np.argmax(spectrum[1:])) + 1])

        self.assertLess(
            abs(dominant_hz - offline_voice.VOICE_SPEECH_CARRIER_HZ),
            8.0,
        )

    def test_ordinary_speech_uses_the_shared_machine_vocoder(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        source = np.zeros(4_000, dtype=np.int16)
        source[400:3_600] = 8_000

        original_vocoder = offline_voice._machine_vocoder
        with mock.patch.object(
            offline_voice,
            "_machine_vocoder",
            wraps=original_vocoder,
        ) as vocoder:
            encoded = offline_voice._encoded_robot_effect(
                np,
                source,
                16_000,
                0.94,
                cadence_strength=0.88,
            )

        self.assertGreater(len(encoded), 0)
        vocoder.assert_called_once()
        self.assertGreater(
            vocoder.call_args.kwargs["cadence_strength"],
            0.0,
        )

    def test_cadence_curve_has_asymmetric_pitch_plateaus(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        energy = np.ones(90, dtype=np.float32)
        curve = offline_voice._cadence_semitone_curve(
            np,
            energy,
            16_000,
            256,
            1.0,
        )

        self.assertEqual(curve.shape, energy.shape)
        self.assertTrue(np.all(np.isfinite(curve)))
        # An unbroken voiced signal still moves through the constrained
        # carrier steps, then lands in a lower phrase-ending plateau.
        self.assertGreater(float(np.max(curve)), 0.5)
        self.assertLess(float(np.min(curve)), -1.3)

    def test_cadence_pattern_matches_reference_jump_depth(self):
        pattern = offline_voice._CADENCE_SEMITONE_PATTERN
        jumps = sorted(
            abs(pattern[(index + 1) % len(pattern)] - value)
            for index, value in enumerate(pattern)
        )
        median_jump = (jumps[2] + jumps[3]) / 2.0

        self.assertEqual(min(pattern), -1.30)
        self.assertEqual(max(pattern), 1.40)
        self.assertGreater(median_jump, 0.70)
        self.assertLess(median_jump, 0.85)
        self.assertLess(pattern[-1], pattern[0])

    def test_clean_pitch_cadence_is_finite_and_uses_variable_speed(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 16_000
        timeline = np.arange(sample_rate, dtype=np.float32) / sample_rate
        source = (
            0.30 * np.sin(2.0 * np.pi * 220.0 * timeline)
            + 0.12 * np.sin(2.0 * np.pi * 440.0 * timeline)
        ).astype(np.float32)
        stepped = offline_voice._clean_pitch_cadence(
            np,
            source,
            sample_rate,
            0.88,
        )

        self.assertEqual(stepped.ndim, 2)
        self.assertEqual(stepped.shape[1], 1)
        self.assertGreater(len(stepped), int(len(source) * 0.80))
        self.assertLess(len(stepped), int(len(source) * 1.20))
        self.assertTrue(np.all(np.isfinite(stepped)))

    def test_pitch_lock_keeps_machine_vocoder_for_singing(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        source = np.zeros(800, dtype=np.int16)

        with mock.patch.object(
            offline_voice,
            "_machine_vocoder",
            return_value=np.zeros((1_600, 1), dtype=np.float32),
        ) as vocoder:
            encoded = offline_voice._encoded_robot_effect(
                np,
                source,
                16_000,
                1.0,
                carrier_hz=220.0,
                output_samples=1_600,
                pitch_lock=True,
            )

        self.assertEqual(len(encoded), 1_600)
        vocoder.assert_called_once()

    def test_machine_vocoder_can_hold_a_sung_note(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 16_000
        source = np.zeros(sample_rate // 10, dtype=np.float32)
        source[100:900] = np.hanning(800).astype(np.float32)
        held = offline_voice._machine_vocoder(
            np,
            source,
            sample_rate,
            carrier_hz=220.0,
            output_samples=sample_rate // 4,
        )

        self.assertEqual(len(held), sample_rate // 4)
        self.assertTrue(np.all(np.isfinite(held)))

    def test_machine_vocoder_applies_feminine_formant_shift(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 16_000
        timeline = np.arange(sample_rate // 5, dtype=np.float32) / sample_rate
        source = (
            np.sin(2.0 * np.pi * 210.0 * timeline)
            + 0.35 * np.sin(2.0 * np.pi * 1_050.0 * timeline)
        ).astype(np.float32)
        neutral = offline_voice._machine_vocoder(
            np,
            source,
            sample_rate,
            carrier_hz=172.0,
            formant_shift=1.0,
        )
        shifted = offline_voice._machine_vocoder(
            np,
            source,
            sample_rate,
            carrier_hz=172.0,
            formant_shift=1.08,
        )

        self.assertEqual(shifted.shape, neutral.shape)
        self.assertTrue(np.all(np.isfinite(shifted)))
        self.assertFalse(np.allclose(shifted, neutral))

    def test_daisy_score_has_notes_rests_and_full_chorus_length(self):
        notes = [item for item in offline_voice.DAISY_CHORUS if item[0]]
        rests = [item for item in offline_voice.DAISY_CHORUS if not item[0]]
        total_seconds = sum(
            item[2] for item in offline_voice.DAISY_CHORUS
        ) * offline_voice.DAISY_EIGHTH_SECONDS

        self.assertGreater(len(notes), 40)
        self.assertTrue(rests)
        self.assertGreater(total_seconds, 35.0)
        self.assertLess(total_seconds, 45.0)

    def test_qwen_continuation_matches_melody_and_extends_performance(self):
        chorus_shape = [
            (note, duration)
            for _text, note, duration in offline_voice.DAISY_CHORUS
        ]
        continuation_shape = [
            (note, duration)
            for _text, note, duration
            in offline_voice.DAISY_QWEN_CONTINUATION
        ]
        total_seconds = sum(
            item[2] for item in offline_voice.DAISY_PERFORMANCE
        ) * offline_voice.DAISY_EIGHTH_SECONDS
        continuation_words = " ".join(
            text
            for text, _note, _duration
            in offline_voice.DAISY_QWEN_CONTINUATION
            if text
        ).lower()
        chorus_words = " ".join(
            text
            for text, _note, _duration in offline_voice.DAISY_CHORUS
            if text
        ).lower()

        self.assertEqual(continuation_shape, chorus_shape)
        self.assertNotEqual(continuation_words, chorus_words)
        self.assertIn("my an sir true", continuation_words)
        self.assertIn("bright ma sheen built for two", continuation_words)
        self.assertGreater(total_seconds, 80.0)
        self.assertLess(total_seconds, 90.0)
        self.assertEqual(
            len(offline_voice.DAISY_PERFORMANCE_CHORDS),
            66,
        )

    def test_daisy_accompaniment_is_audible_bounded_and_synchronized(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        sample_rate = 8_000
        vocal_samples = int(
                round(
                sum(item[2] for item in offline_voice.DAISY_PERFORMANCE)
                * offline_voice.DAISY_EIGHTH_SECONDS
                * sample_rate
            )
        )
        backing = offline_voice._daisy_computer_accompaniment(
            np,
            sample_rate,
            vocal_samples,
        )

        self.assertEqual(len(offline_voice.DAISY_CHORD_PROGRESSION), 32)
        self.assertEqual(len(offline_voice.DAISY_PERFORMANCE_CHORDS), 66)
        self.assertEqual(backing.shape, (vocal_samples,))
        self.assertEqual(backing.dtype, np.float32)
        self.assertTrue(np.all(np.isfinite(backing)))
        self.assertGreater(float(np.max(np.abs(backing))), 0.05)
        self.assertLessEqual(float(np.max(np.abs(backing))), 0.58)

        vocal = (
            np.sin(
                np.arange(vocal_samples, dtype=np.float32)
                * (2.0 * np.pi * 172.0 / sample_rate)
            )
            * 11_000
        ).astype(np.int16)
        mixed = offline_voice._mix_daisy_performance(
            np,
            vocal,
            sample_rate,
        )

        self.assertEqual(mixed.shape, vocal.shape)
        self.assertEqual(mixed.dtype, np.int16)
        self.assertLessEqual(int(np.max(np.abs(mixed))), 32_767)


class MusicVisualizerTests(unittest.TestCase):
    def _features(self):
        return {
            "bass": 0.82,
            "mid": 0.57,
            "treble": 0.71,
            "level": 0.68,
            "beat": 0.55,
            "stereo_width": 0.42,
            "pan": -0.15,
            "waveform": [
                0.0, 0.45, -0.3, 0.75, -0.65, 0.25, -0.1, 0.0,
            ],
            "spectrum": [
                (index % 7) / 6.0
                for index in range(48)
            ],
        }

    def test_radial_scene_fills_requested_terminal_shape(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        palette = tuple(f"color-{index}" for index in range(9))
        visualizer = RadialVisualizer(palette)
        features = self._features()
        visualizer.step(0.08, features, 48, 16)
        frame = visualizer.render(48, 16, features)

        self.assertEqual(len(frame), 16)
        self.assertTrue(all(len(row) == 48 for row in frame))
        cells = [cell for row in frame for cell in row if cell]
        self.assertTrue(cells)
        self.assertTrue(
            all(0x2800 <= ord(cell[0]) <= 0x28FF for cell in cells)
        )

    def test_waveform_uses_brightest_palette_entry(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        palette = tuple(f"color-{index}" for index in range(9))
        visualizer = RadialVisualizer(palette)
        features = self._features()
        frame = visualizer.render(40, 12, features)

        self.assertTrue(
            any(
                cell and cell[1] == palette[-1]
                for row in frame
                for cell in row
            )
        )

    def test_radial_scene_handles_silence_and_tiny_viewport(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        visualizer = RadialVisualizer(("dim", "bright"))
        frame = visualizer.render(1, 1, {})

        self.assertEqual(len(frame), 1)
        self.assertEqual(len(frame[0]), 1)

    def test_added_scenes_fill_requested_terminal_shape(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is installed by the optional voice setup")

        palette = tuple(f"color-{index}" for index in range(9))
        features = self._features()

        for scene_class in (SpectrumVisualizer, ReactorVisualizer):
            with self.subTest(scene=scene_class.__name__):
                visualizer = scene_class(palette)
                visualizer.step(0.08, features, 48, 16)
                frame = visualizer.render(48, 16, features)
                self.assertEqual(len(frame), 16)
                self.assertTrue(all(len(row) == 48 for row in frame))
                self.assertTrue(any(cell for row in frame for cell in row))


class AudioModeUiTests(unittest.TestCase):
    def tearDown(self):
        ui._engine.current_input = ""
        ui._engine.cycle_index = -1
        ui._engine.music_mode = False
        ui._engine.music_visualizer = None
        ui._engine.music_audio = None
        ui._engine.music_status = ""
        ui._engine.music_palette_index = 0
        ui._engine.music_scene_index = 0
        ui._engine.music_volume_percent = 100
        ui._engine._music_scene_started_at = 0.0
        ui.set_voice_mode(False)

    def test_live_input_reports_lines_and_escape_separately(self):
        ui.begin_input("AUDIO >")

        with mock.patch.object(
            ui,
            "get_char",
            side_effect=["h", "i", "\r", "ESC"],
        ):
            self.assertIsNone(ui.poll_input_event())
            self.assertIsNone(ui.poll_input_event())
            self.assertEqual(ui.poll_input_event(), ("line", "hi"))
            self.assertEqual(ui.poll_input_event(), ("escape", None))

    def test_voice_face_is_larger_than_normal_face(self):
        engine = ui.LayeredDisplayEngine()
        base = engine._build_face_pixels(0, 0.0)
        enlarged = engine._scale_pixel_buffer(
            base,
            ui.VOICE_FACE_PIXEL_W,
            ui.VOICE_FACE_PIXEL_H,
        )
        rows = engine._braille_rows(enlarged)

        self.assertGreater(len(rows), ui.FACE_CELL_H)
        self.assertGreater(len(rows[0]), ui.FACE_CELL_W)

    def test_voice_face_uses_regular_header_palette_and_effects(self):
        engine = ui.LayeredDisplayEngine()
        engine.width = 80
        engine.height = 24
        engine.voice_mode = True
        canvas = [
            [ui.CanvasCell() for _ in range(engine.width)]
            for _ in range(engine.height)
        ]

        with mock.patch.object(
            engine,
            "_header_effect_cell",
        ) as effect:
            engine.draw_header(canvas, heat=0.3)

        face_left = (engine.width - ui.VOICE_FACE_CELL_W) // 2
        face_calls = [
            call.kwargs
            for call in effect.call_args_list
            if (
                call.kwargs["y"] < ui.VOICE_FACE_CELL_H
                and face_left
                <= call.kwargs["x"]
                < face_left + ui.VOICE_FACE_CELL_W
            )
        ]

        self.assertTrue(face_calls)
        self.assertTrue(
            all(call["base_color"] == ui.WHITE for call in face_calls)
        )
        self.assertTrue(
            all(call["heat"] == 0.3 for call in face_calls)
        )

    def test_compact_audio_face_does_not_overlap_input_row(self):
        engine = ui.LayeredDisplayEngine()
        engine.width = 40
        engine.height = 15
        engine.voice_mode = True
        canvas = [
            [ui.CanvasCell() for _ in range(engine.width)]
            for _ in range(engine.height)
        ]

        engine.draw_header(canvas, heat=0.3)

        self.assertLessEqual(engine.header_height, engine.height - 3)

    def test_speaking_flag_only_applies_inside_audio_mode(self):
        ui.set_voice_speaking(True)
        self.assertFalse(ui._engine.voice_speaking)

        ui.set_voice_mode(True)
        ui.set_voice_speaking(True)
        self.assertTrue(ui._engine.voice_speaking)

    def test_space_cycles_visualizer_palette_without_typing(self):
        engine = ui._engine
        engine.music_mode = True
        engine.music_visualizer = SimpleNamespace(
            palette=engine._MUSIC_PALETTES[0][1]
        )
        engine.music_palette_index = 0
        engine.current_input = "keep this draft"

        with mock.patch.object(ui, "get_char", return_value=" "):
            self.assertIsNone(ui.poll_input_event())

        self.assertEqual(engine.music_palette_index, 1)
        self.assertEqual(
            engine.music_visualizer.palette,
            tuple(engine._MUSIC_PALETTES[1][1]),
        )
        self.assertEqual(engine.current_input, "keep this draft")
        self.assertIn("ultraviolet", engine.music_status)

    def test_palette_cycle_does_not_start_music_mode(self):
        ui._engine.music_mode = False
        ui._engine.music_visualizer = None

        self.assertEqual(ui.cycle_music_palette(), "Music mode is off.")

    def test_arrow_keys_cycle_visualizer_scenes_without_typing(self):
        engine = ui._engine
        engine.music_mode = True
        engine.music_scene_index = 0
        engine.music_visualizer = SimpleNamespace(palette=())
        engine.current_input = "keep this draft"

        with mock.patch.object(
            ui,
            "_make_music_scene",
            return_value=SimpleNamespace(palette=()),
        ), mock.patch.object(ui, "get_char", return_value="RIGHT"):
            self.assertIsNone(ui.poll_input_event())

        self.assertEqual(engine.music_scene_index, 1)
        self.assertEqual(engine.current_input, "keep this draft")
        self.assertIn("spectrum cathedral", engine.music_status)

    def test_volume_command_is_visible_without_developer_mode(self):
        with mock.patch.object(ui, "set_music_volume", return_value=70) as setter:
            result = command_handlers.try_handle_command("volume 70")

        setter.assert_called_once_with(70)
        self.assertIn("70%", result)
        entry = next(c for c in command_handlers.COMMANDS if c["name"] == "volume")
        self.assertFalse(entry["dev_only"])


class PromptEfficiencyTests(unittest.TestCase):
    def test_runtime_context_does_not_change_the_cacheable_system_prefix(self):
        with mock.patch.object(
            assistant_main.memory_logic,
            "select_relevant",
            side_effect=lambda _memories, text, limit=4: (
                [] if not text else [{"memory": "Relevant project fact."}]
            ),
        ):
            cached = assistant_main._base_prompt_messages("", None)
            live = assistant_main._base_prompt_messages(
                "Tell me about the project.",
                None,
        )

        self.assertEqual(cached[0], live[0])
        self.assertNotEqual(cached[1]["content"], live[1]["content"])
        self.assertTrue(cached[1]["content"].startswith("Runtime context"))

    def test_greeting_does_not_select_unrelated_memories(self):
        memories = [
            {
                "memory": "The developer owns a Raspberry Pi 5.",
                "confidence": 0.9,
            }
        ]
        self.assertEqual(memory_logic.select_relevant(memories, "hey"), [])

    def test_trivial_chat_skips_memory_inference(self):
        for message in ("hey", "thanks, that worked", "how are you?"):
            with self.subTest(message=message):
                self.assertFalse(
                    memory_extractor.looks_like_durable_fact(message)
                )

    def test_durable_statement_reaches_memory_inference(self):
        self.assertTrue(
            memory_extractor.looks_like_durable_fact(
                "I own a Raspberry Pi 5 and use it for this project"
            )
        )

    def test_prompt_cache_name_changes_with_stable_prompt(self):
        fake_stat = SimpleNamespace(st_size=123, st_mtime_ns=456)

        with (
            mock.patch.object(assistant_main.os, "stat", return_value=fake_stat),
            mock.patch.object(
                assistant_main,
                "_base_prompt_messages",
                return_value=[{"role": "system", "content": "stable prompt one"}],
            ),
        ):
            first = assistant_main._prompt_cache_filename()

        with (
            mock.patch.object(assistant_main.os, "stat", return_value=fake_stat),
            mock.patch.object(
                assistant_main,
                "_base_prompt_messages",
                return_value=[{"role": "system", "content": "stable prompt two"}],
            ),
        ):
            second = assistant_main._prompt_cache_filename()

        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("torment-nexus-prefix-"))


class WorkerLifecycleTests(unittest.TestCase):
    def tearDown(self):
        memory_worker.stop(drain_seconds=0)

    def test_worker_can_restart_without_replaying_dropped_work(self):
        processed = []
        gate = threading.Event()

        def slow_process(user, reply):
            gate.wait(0.2)
            processed.append((user, reply))

        with mock.patch.object(memory_worker, "IDLE_GRACE_SECONDS", 0):
            memory_worker.start(slow_process)
            memory_worker.submit("first", "reply")
            memory_worker.submit("drop me", "reply")
            time.sleep(0.02)
            memory_worker.stop(drain_seconds=0)
            gate.set()

            memory_worker.start(
                lambda user, reply: processed.append((user, reply))
            )
            memory_worker.submit("new", "reply")

            deadline = time.time() + 1
            while memory_worker.pending() and time.time() < deadline:
                time.sleep(0.01)

        self.assertIn(("new", "reply"), processed)
        self.assertNotIn(("drop me", "reply"), processed)


class ServerOwnershipTests(unittest.TestCase):
    def test_reloaded_process_stops_owned_server(self):
        old = os.environ.get(llm_server._OWNED_PID_ENV)
        os.environ[llm_server._OWNED_PID_ENV] = "12345"

        try:
            with mock.patch.object(llm_server.os, "kill") as kill:
                llm_server.stop_server(None)
                kill.assert_called_once_with(12345, llm_server.signal.SIGTERM)
        finally:
            if old is None:
                os.environ.pop(llm_server._OWNED_PID_ENV, None)
            else:
                os.environ[llm_server._OWNED_PID_ENV] = old


class SpotifyDesktopTests(unittest.TestCase):
    def setUp(self):
        self.original_desktop = command_handlers._spotify_desktop
        command_handlers._spotify_desktop = None
        self.addCleanup(self._restore_desktop)

    def _restore_desktop(self):
        command_handlers._spotify_desktop = self.original_desktop

    def test_desktop_search_uses_spotify_protocol_not_web_api(self):
        with mock.patch.object(
            spotify_control,
            "_spotify_executable",
            return_value=r"C:\\Spotify\\Spotify.exe",
        ), mock.patch.object(
            spotify_control,
            "_launch_desktop_client",
            return_value=True,
        ) as launch, mock.patch.object(
            spotify_control.SpotifyDesktop,
            "_open_uri",
            return_value=True,
        ) as open_uri:
            result = spotify_control.SpotifyDesktop.search("dark break core")

        launch.assert_called_once_with()
        open_uri.assert_called_once_with("spotify:search:dark%20break%20core")
        self.assertEqual(result, "Opened Spotify search: dark break core")

    def test_desktop_launch_is_honest_when_spotify_is_missing(self):
        with mock.patch.object(
            spotify_control,
            "_spotify_executable",
            return_value=None,
        ):
            with self.assertRaisesRegex(
                spotify_control.SpotifyError,
                "No Spotify desktop client",
            ):
                spotify_control.SpotifyDesktop.launch()

    def test_spotify_search_uses_metadata_picker_not_the_web_api(self):
        tracks = [{
            "title": "Breakcore Test",
            "artist": "Example Artist",
            "release": "Example Release",
            "year": "2026",
            "length_ms": 120000,
        }]

        with mock.patch.object(
            music_metadata,
            "search_recordings",
            return_value=tracks,
        ) as search, mock.patch.object(command_handlers, "_get_spotify") as remote:
            result = command_handlers.try_handle_command("spotify search breakcore")

        search.assert_called_once_with("breakcore", limit=5)
        remote.assert_not_called()
        self.assertIn("MUSIC RESULTS", result)
        self.assertIn("Breakcore Test - Example Artist", result)

    def test_natural_spotify_requests_route_to_the_local_command(self):
        self.assertTrue(natural_command.looks_like_command_request("open Spotify"))
        self.assertEqual(
            natural_command._deterministic("search Spotify for breakcore", False),
            "spotify search breakcore",
        )
        self.assertEqual(
            natural_command._deterministic("find breakcore on Spotify", False),
            "spotify search breakcore",
        )


class SpotifyPickerTests(unittest.TestCase):
    TRACKS = [
        {
            "title": "Daisy",
            "artist": "Harry Dacre",
            "release": "Music Hall",
            "year": "1892",
            "length_ms": 174000,
        },
        {
            "title": "Daisy Bell Rework",
            "artist": "Example Artist",
            "release": "Machine Songs",
            "year": "2026",
            "length_ms": 201000,
        },
    ]

    def setUp(self):
        self.original_selection = command_handlers._spotify_pending_selection
        command_handlers._spotify_pending_selection = None
        self.addCleanup(self._restore_selection)

    def _restore_selection(self):
        command_handlers._spotify_pending_selection = self.original_selection

    def test_search_renders_choices_then_numeric_reply_opens_local_spotify(self):
        desktop = mock.Mock()
        desktop.search.return_value = (
            "Opened Spotify search: Daisy Bell Rework - Example Artist"
        )

        with mock.patch.object(
            music_metadata,
            "search_recordings",
            return_value=self.TRACKS,
        ) as search, mock.patch.object(
            command_handlers,
            "_get_spotify_desktop",
            return_value=desktop,
        ), mock.patch.object(command_handlers, "_get_spotify") as remote:
            results = command_handlers.try_handle_command("spotify search daisy")
            chosen = command_handlers.try_handle_command("2")

        search.assert_called_once_with("daisy", limit=5)
        remote.assert_not_called()
        desktop.search.assert_called_once_with("Daisy Bell Rework - Example Artist")
        self.assertIn("[1] Daisy - Harry Dacre", results)
        self.assertIn("[2] Daisy Bell Rework - Example Artist", results)
        self.assertIn("Reply with a number", results)
        self.assertIn("Opened Spotify search", chosen)
        self.assertIn("Choose the matching result there", chosen)
        self.assertIsNone(command_handlers._spotify_pending_selection)

    def test_invalid_number_keeps_the_picker_and_cancel_clears_it(self):
        command_handlers._spotify_pending_selection = {
            "query": "daisy",
            "tracks": self.TRACKS,
            "expires_at": time.monotonic() + 60,
        }

        invalid = command_handlers.try_handle_command("6")
        cancelled = command_handlers.try_handle_command("spotify cancel")

        self.assertIn("1 to 2", invalid)
        self.assertEqual(cancelled, "Spotify selection cancelled.")
        self.assertIsNone(command_handlers._spotify_pending_selection)

    def test_local_spotify_error_is_shown_honestly(self):
        command_handlers._spotify_pending_selection = {
            "query": "daisy",
            "tracks": self.TRACKS,
            "expires_at": time.monotonic() + 60,
        }
        desktop = mock.Mock()
        desktop.search.side_effect = spotify_control.SpotifyError(
            "Spotify was found but could not be started."
        )

        with mock.patch.object(
            command_handlers,
            "_get_spotify_desktop",
            return_value=desktop,
        ):
            result = command_handlers.try_handle_command("1")

        desktop.search.assert_called_once_with("Daisy - Harry Dacre")
        self.assertIn("SPOTIFY (LOCAL)", result)
        self.assertIn("could not be started", result)


class MusicMetadataTests(unittest.TestCase):
    def setUp(self):
        self.original_cache = music_metadata._cache
        self.original_last_request_at = music_metadata._last_request_at
        music_metadata._cache = {}
        music_metadata._last_request_at = 0.0
        self.addCleanup(self._restore_metadata_state)

    def _restore_metadata_state(self):
        music_metadata._cache = self.original_cache
        music_metadata._last_request_at = self.original_last_request_at

    def test_lookup_sends_plain_query_and_returns_minimal_recording_data(self):
        response = mock.Mock()
        response.json.return_value = {
            "recordings": [{
                "title": "Daisy",
                "artist-credit": [{"name": "Harry Dacre"}],
                "releases": [{"title": "Music Hall", "date": "1892-01-01"}],
                "length": 174000,
                "unneeded": "not kept",
            }]
        }

        with mock.patch.object(
            music_metadata.requests,
            "get",
            return_value=response,
        ) as get:
            results = music_metadata.search_recordings("  daisy   bell  ", limit=99)

        response.raise_for_status.assert_called_once_with()
        get.assert_called_once_with(
            music_metadata.SEARCH_URL,
            params={"query": "daisy bell", "fmt": "json", "limit": 5,
                    "dismax": "true"},
            headers={"User-Agent": music_metadata.USER_AGENT,
                     "Accept": "application/json"},
            timeout=music_metadata.TIMEOUT_SECONDS,
        )
        self.assertEqual(results, [{
            "title": "Daisy",
            "artist": "Harry Dacre",
            "release": "Music Hall",
            "year": "1892",
            "length_ms": 174000,
        }])

    def test_lookup_uses_short_lived_cache(self):
        response = mock.Mock()
        response.json.return_value = {"recordings": []}

        with mock.patch.object(
            music_metadata.requests,
            "get",
            return_value=response,
        ) as get:
            self.assertEqual(music_metadata.search_recordings("daisy"), [])
            self.assertEqual(music_metadata.search_recordings("DAISY"), [])

        get.assert_called_once()


class LocalMusicTests(unittest.TestCase):
    """
    The local library is the only music path that works with no network,
    so the tests that matter are the ones proving it never depends on
    Spotify and never loses a name race to it.
    """

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        patcher = mock.patch.object(config, "MUSIC_LIBRARY_DIR", self.folder)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(local_player.get_player().stop)

    def _add(self, filename):
        path = os.path.join(self.folder, filename)

        with open(path, "wb") as handle:
            handle.write(b"\0")

        return path

    def test_only_decodable_audio_is_offered_as_a_track(self):
        self._add("breakcore.mp3")
        self._add("notes.txt")
        self._add("cover.png")

        self.assertEqual(
            [name for name, _ in local_player.available_tracks()],
            ["breakcore"],
        )

    def test_partial_and_mixed_case_names_resolve(self):
        self._add("breakcore.mp3")

        for query in ("breakcore", "BreakCore", "break", "core"):
            match, ambiguous = local_player.find_track(query)
            self.assertIsNotNone(match, query)
            self.assertEqual(match[0], "breakcore")
            self.assertEqual(ambiguous, [])

    def test_ambiguous_name_is_reported_rather_than_guessed(self):
        self._add("breakcore.mp3")
        self._add("breakbeat.mp3")

        match, ambiguous = local_player.find_track("break")

        self.assertIsNone(match)
        self.assertEqual(sorted(ambiguous), ["breakbeat", "breakcore"])

    def test_exact_name_still_wins_when_others_contain_it(self):
        self._add("core.mp3")
        self._add("breakcore.mp3")

        match, ambiguous = local_player.find_track("core")

        self.assertIsNotNone(match)
        self.assertEqual(match[0], "core")
        self.assertEqual(ambiguous, [])

    def test_playing_a_local_track_never_reaches_spotify(self):
        self._add("breakcore.mp3")
        played = {}

        def fake_play(name, path):
            played["name"] = name
            return True

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            with mock.patch.object(
                local_player.get_player(), "play", side_effect=fake_play
            ):
                with mock.patch.object(
                    local_player.get_player(), "position", return_value=(0.0, 90.0)
                ):
                    result = command_handlers.try_handle_command("play breakcore")

            spotify.assert_not_called()

        self.assertEqual(played.get("name"), "breakcore")
        self.assertIn("breakcore", result)

    def test_unknown_name_falls_through_to_spotify(self):
        self._add("breakcore.mp3")

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            spotify.return_value.play_track.return_value = "Playing something"
            command_handlers.try_handle_command("play a track that is not local")

        spotify.return_value.play_track.assert_called_once_with(
            "a track that is not local"
        )

    def test_play_playlist_is_not_captured_by_the_local_library(self):
        self._add("breakcore.mp3")

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            spotify.return_value.play_playlist.return_value = "Playing playlist"
            command_handlers.try_handle_command("play playlist breakcore")

        spotify.return_value.play_playlist.assert_called_once_with("breakcore")

    def test_pause_and_resume_prefer_local_playback_when_it_is_running(self):
        player = local_player.get_player()

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            with mock.patch.object(player, "pause", return_value=True):
                with mock.patch.object(
                    player, "position", return_value=(5.0, 90.0)
                ):
                    with mock.patch.object(
                        player, "current_track", return_value="breakcore"
                    ):
                        self.assertIn(
                            "breakcore",
                            command_handlers.try_handle_command("pause"),
                        )

            with mock.patch.object(player, "resume", return_value=True):
                with mock.patch.object(
                    player, "current_track", return_value="breakcore"
                ):
                    self.assertIn(
                        "breakcore",
                        command_handlers.try_handle_command("resume"),
                    )

            spotify.assert_not_called()

    def test_explicit_local_suffix_never_falls_back_to_spotify(self):
        player = local_player.get_player()

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            # Nothing local is playing, so these would silently hit Spotify
            # if the suffix were not honoured.
            self.assertEqual(
                command_handlers.try_handle_command("pause local"),
                "Nothing is playing locally.",
            )
            self.assertEqual(
                command_handlers.try_handle_command("resume local"),
                "No local track is paused.",
            )
            spotify.assert_not_called()

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            with mock.patch.object(player, "pause", return_value=True):
                with mock.patch.object(
                    player, "position", return_value=(5.0, 90.0)
                ):
                    with mock.patch.object(
                        player, "current_track", return_value="breakcore"
                    ):
                        self.assertIn(
                            "breakcore",
                            command_handlers.try_handle_command("pause local"),
                        )
            spotify.assert_not_called()

    def test_explicit_spotify_suffix_never_touches_local_playback(self):
        player = local_player.get_player()

        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            spotify.return_value.pause.return_value = "Paused"
            spotify.return_value.resume.return_value = "Resumed"

            with mock.patch.object(player, "pause") as local_pause:
                with mock.patch.object(player, "resume") as local_resume:
                    command_handlers.try_handle_command("pause spotify")
                    command_handlers.try_handle_command("resume spotify")

                    local_pause.assert_not_called()
                    local_resume.assert_not_called()

        spotify.return_value.pause.assert_called_once_with()
        spotify.return_value.resume.assert_called_once_with()

    def test_suffixed_commands_are_not_swallowed_by_the_bare_ones(self):
        registered = [c["name"] for c in command_handlers.COMMANDS]

        for name in ("pause local", "pause spotify",
                     "resume local", "resume spotify"):
            self.assertIn(name, registered)

        # "pause local" must not be matched by the bare "pause" handler.
        self.assertFalse(command_handlers.handle_pause("pause local"))
        self.assertFalse(command_handlers.handle_resume("resume spotify"))

    def test_pause_falls_back_to_spotify_when_nothing_local_is_playing(self):
        with mock.patch.object(command_handlers, "_get_spotify") as spotify:
            spotify.return_value.pause.return_value = "Paused"
            command_handlers.try_handle_command("pause")

        spotify.return_value.pause.assert_called_once_with()

    def test_stop_music_is_honest_when_nothing_is_playing(self):
        self.assertEqual(
            command_handlers.try_handle_command("stop music"),
            "Nothing is playing locally.",
        )

    def test_plain_stop_targets_only_active_local_playback(self):
        player = local_player.get_player()

        with mock.patch.object(player, "is_loaded", return_value=True), \
            mock.patch.object(player, "current_track", return_value="breakcore"), \
            mock.patch.object(player, "stop", return_value=True) as stop:
            result = command_handlers.try_handle_command("stop")

        self.assertEqual(result, "Stopped breakcore.")
        stop.assert_called_once_with()

        with mock.patch.object(player, "is_loaded", return_value=False):
            self.assertIsNone(command_handlers.try_handle_command("stop"))

    def test_empty_library_explains_where_files_go(self):
        result = command_handlers.try_handle_command("music library")

        self.assertIn(self.folder, result)
        self.assertIn("play <filename>", result)

    def test_music_commands_work_without_developer_mode(self):
        for name in ("music library", "stop music"):
            entry = next(c for c in command_handlers.COMMANDS if c["name"] == name)
            self.assertFalse(entry["dev_only"], name)


class TutorialTests(unittest.TestCase):
    """
    The tutorial's one real risk is drifting out of date, so these check
    that it stays tied to the live command registry rather than keeping
    its own copy of what TORMENT_NEXUS can do.
    """

    def setUp(self):
        self.state = os.path.join(tempfile.mkdtemp(), "tutorial.json")
        patcher = mock.patch.object(tutorial, "STATE_FILE", self.state)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_referenced_command_actually_exists(self):
        catalog = {e["name"] for e in command_handlers.command_catalog()}
        missing = [
            f"{lesson['key']}:{name}"
            for lesson in tutorial.LESSONS
            for name in lesson["commands"]
            if name not in catalog
        ]

        self.assertEqual(missing, [], "tutorial names commands that are gone")

    def test_descriptions_come_from_the_registry(self):
        entry = next(e for e in command_handlers.command_catalog()
                     if e["name"] == "music library")
        rendered = "\n".join(
            tutorial.render_lesson(i) for i in range(len(tutorial.LESSONS)))

        self.assertIn(entry["description"], rendered)

    def test_new_user_sections_cover_projects_and_goals(self):
        lessons = {lesson["key"]: lesson for lesson in tutorial.LESSONS}

        self.assertEqual(
            lessons["projects"]["commands"],
            ["build project", "list projects", "dump path"],
        )
        self.assertEqual(
            lessons["goals"]["commands"],
            ["goals", "set goals", "work on goals", "goal done"],
        )

    def test_tutorial_mentions_voice_first_and_visualizer_controls(self):
        self.assertIn("say it instead", tutorial.first_run_invitation())
        music = next(lesson for lesson in tutorial.LESSONS
                     if lesson["key"] == "music")["body"]
        self.assertIn("Space", music)
        self.assertIn("Ctrl+B", music)
        self.assertIn("2:45", music)
        self.assertIn("Left/Right", music)

    def test_tutorial_explains_the_spotify_number_picker(self):
        lesson = next(lesson for lesson in tutorial.LESSONS
                      if lesson["key"] == "music")

        self.assertIn("spotify search", lesson["body"])
        self.assertIn("1 through 5", lesson["body"])
        self.assertIn("MusicBrainz", lesson["body"])
        self.assertIn("spotify", lesson["commands"])

    def test_tutorial_qualifies_web_and_radio_privacy(self):
        what = next(lesson for lesson in tutorial.LESSONS
                    if lesson["key"] == "what")["body"]
        hardware = next(lesson for lesson in tutorial.LESSONS
                        if lesson["key"] == "hardware")["body"]

        self.assertIn("deliberate exception", what)
        self.assertIn("non-secret", hardware)

    def test_a_vanished_command_is_flagged_not_invented(self):
        broken = dict(tutorial.LESSONS[0])
        broken["commands"] = ["help", "command that does not exist"]

        with mock.patch.object(tutorial, "LESSONS",
                               [broken] + tutorial.LESSONS[1:]):
            text = tutorial.render_lesson(0)

        self.assertIn("no longer available", text)

    def test_first_run_is_detected_once(self):
        self.assertTrue(tutorial.is_first_run())
        tutorial.mark_seen()
        self.assertFalse(tutorial.is_first_run())

    def test_navigation_stays_in_range(self):
        tutorial.set_position(9999)
        self.assertEqual(tutorial.position(), len(tutorial.LESSONS) - 1)
        tutorial.set_position(-5)
        self.assertEqual(tutorial.position(), 0)

        self.assertIn("numbered 1 to",
                      command_handlers.try_handle_command("tutorial 99"))

    def test_bare_next_only_advances_an_active_tutorial(self):
        tutorial.reset()
        tutorial.set_position(0)

        result = command_handlers.try_handle_command("next")

        self.assertIn("TUTORIAL  2/", result)
        self.assertIn("TUTORIAL  3/", result)
        self.assertEqual(tutorial.position(), 2)

        tutorial.set_position(len(tutorial.LESSONS) - 1)
        self.assertFalse(command_handlers.handle_tutorial("next"))

    def test_restart_and_next_render_two_lesson_batches(self):
        first = command_handlers.try_handle_command("tutorial restart")

        self.assertIn("TUTORIAL  1/", first)
        self.assertIn("TUTORIAL  2/", first)
        self.assertEqual(tutorial.position(), 1)
        self.assertIn("next two sections", first)

        second = command_handlers.try_handle_command("tutorial next")

        self.assertIn("TUTORIAL  3/", second)
        self.assertIn("TUTORIAL  4/", second)
        self.assertEqual(tutorial.position(), 3)

    def test_explain_returns_none_for_unknown_topics(self):
        # Falling through to the model beats inventing a feature.
        self.assertIsNone(tutorial.explain("quantum bicycle maintenance"))
        self.assertFalse(
            command_handlers.handle_explain_topic("explain a nonexistent thing"))

    def test_explain_covers_commands_and_subsystems(self):
        self.assertIn("developer mode", tutorial.explain("suggest").lower())
        self.assertIn("Speaking and listening", tutorial.explain("voice"))

    def test_explain_file_still_belongs_to_the_file_reader(self):
        # 'explain file <path>' predates this and must not be swallowed.
        self.assertFalse(
            command_handlers.handle_explain_topic("explain file main.py"))

    def test_tutorial_and_explain_need_no_developer_mode(self):
        for name in ("tutorial", "explain"):
            entry = next(c for c in command_handlers.COMMANDS
                         if c["name"] == name)
            self.assertFalse(entry["dev_only"], name)


class GlitchLabelTests(unittest.TestCase):
    """The desktop label animation must never produce an unusable name."""

    def test_every_frame_is_exactly_the_resting_width(self):
        widths = {len(glitch_icon.scramble_label(step / 20.0))
                  for step in range(21)}

        self.assertEqual(widths, {glitch_icon.NAME_WIDTH})

    def test_fully_settled_is_the_real_name(self):
        self.assertEqual(glitch_icon.scramble_label(1.0),
                         glitch_icon.RESTING_LABEL)

    def test_noise_is_filename_safe(self):
        illegal = set('\\/:*?"<>|')
        sample = "".join(glitch_icon.scramble_label(0.0) for _ in range(300))

        self.assertFalse(set(sample) & illegal)

    def test_resolve_locks_left_to_right(self):
        half = glitch_icon.scramble_label(0.5)
        locked = glitch_icon.NAME_WIDTH // 2

        self.assertEqual(half[:locked], glitch_icon.RESTING_LABEL[:locked])


class ConversationalPhrasingTests(unittest.TestCase):
    """
    Ordinary sentences must not be mistaken for command invocations.

    "do it again" was answered with "Developer mode is required for:
    do <number>". The handler itself was careful, but the developer gate
    ran first and only checked that an argument existed, not that it
    looked like one.
    """

    def setUp(self):
        patcher = mock.patch.object(command_handlers, "DEV_MODE", False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _blocked(self, text):
        result = command_handlers.try_handle_command(text)
        return bool(result and "Developer mode is required" in result)

    def test_plain_english_is_not_refused_as_a_command(self):
        for phrase in (
            "do it again",
            "do you like music",
            "do you remember what I said",
            "do that thing we talked about",
            "read file this book later",
            "explain file that to me",
            "rollback that thought",
            "modify plan for dinner tonight",
            "backup file cabinets are full",
        ):
            self.assertFalse(self._blocked(phrase), phrase)

    def test_real_invocations_still_require_developer_mode(self):
        for phrase in (
            "do 1",
            "read file main.py",
            "explain file core/config.py",
            "rollback main.py.20260101",
            "modify plan main.py add a docstring",
        ):
            self.assertTrue(self._blocked(phrase), phrase)

    def test_file_commands_still_accept_trailing_arguments(self):
        # "read file main.py lines 5-40" is valid; the pattern must not
        # have narrowed the argument to a single bare token.
        self.assertTrue(self._blocked("read file main.py lines 5-40"))

    def test_argument_patterns_are_published_in_the_catalog(self):
        entry = next(e for e in command_handlers.command_catalog()
                     if e["name"] == "do")
        self.assertEqual(entry["arg_pattern"], r"^\d+$")


class PlaybackStopTests(unittest.TestCase):
    """Audio must always remain stoppable."""

    class _Stream:
        def __init__(self):
            self.active = True

    class _Sd:
        def __init__(self, stream=None, raises=False):
            self._stream = stream
            self._raises = raises
            self.stopped = False

        def play(self, *args, **kwargs):
            pass

        def get_stream(self):
            if self._raises:
                raise RuntimeError("no current stream")
            return self._stream

        def stop(self):
            self.stopped = True
            if self._stream is not None:
                self._stream.active = False

    def _voice(self, sd):
        voice = offline_voice.OfflineVoice.__new__(offline_voice.OfflineVoice)
        voice.output_device = None
        voice.sd = sd
        return voice

    def _silence(self):
        import numpy as np

        return np.zeros(1000, dtype=np.int16)

    def test_cancel_stops_playback(self):
        sd = self._Sd(self._Stream())
        voice = self._voice(sd)

        self.assertFalse(
            voice._play_audio(self._silence(), 22050, cancelled=lambda: True))
        self.assertTrue(sd.stopped)

    def test_a_broken_stream_query_does_not_strand_audio(self):
        # Previously this raised out of _play_audio, abandoning the loop
        # that honours the cancel key while sound kept playing.
        sd = self._Sd(raises=True)
        voice = self._voice(sd)

        self.assertFalse(
            voice._play_audio(self._silence(), 22050, cancelled=lambda: True))
        self.assertTrue(sd.stopped)

    def test_a_stream_that_never_ends_cannot_pin_the_loop_open(self):
        sd = self._Sd(self._Stream())
        voice = self._voice(sd)

        import numpy as np

        # 0.05s of audio; the deadline is duration + 5s, so this returns
        # rather than looping forever on a stream stuck at active=True.
        started = time.monotonic()
        voice._play_audio(np.zeros(1102, dtype=np.int16), 22050,
                          cancelled=lambda: False)

        self.assertLess(time.monotonic() - started, 20.0)
        self.assertTrue(sd.stopped)


class GlitchRecoveryTests(unittest.TestCase):
    """The animator must never delete a shortcut it did not create."""

    def test_ownership_needs_a_generated_looking_name(self):
        self.assertFalse(glitch_icon._looks_scrambled("launchmod_eldenring"))
        self.assertFalse(glitch_icon._looks_scrambled("Spotify"))
        self.assertFalse(glitch_icon._looks_scrambled("short"))

    def test_generated_names_are_recognised(self):
        for _ in range(20):
            self.assertTrue(
                glitch_icon._looks_scrambled(glitch_icon.scramble_label(0.0)))
        self.assertTrue(
            glitch_icon._looks_scrambled(glitch_icon.RESTING_LABEL))

    def test_recovery_never_calls_remove(self):
        source = inspect.getsource(glitch_icon._recover_orphans)
        self.assertNotIn("os.remove", source)
        self.assertIn("shutil.move", source)


class SelfEditBoundaryTests(unittest.TestCase):
    """
    The editor must not be able to weaken the things that judge it.

    edit_guard already denies main.py and command_handlers.py on the
    grounds that an editor which can rewrite the approval gate makes
    approval theatre. These pin the same argument to the two other files
    that decide whether a change was acceptable.
    """

    def test_the_persona_cannot_be_edited(self):
        # Injected into every prompt, and holds the honesty and refusal
        # rules. Softening it would be approved as a diff like any other.
        self.assertNotIn(
            os.path.join("core", "persona.py").replace(os.sep, "/"),
            [p.replace(os.sep, "/") for p in edit_guard.list_editable_files()],
        )

    def test_the_test_suite_cannot_be_edited(self):
        # A suite the subject can rewrite stops being evidence.
        editable = [p.replace(os.sep, "/")
                    for p in edit_guard.list_editable_files()]

        self.assertFalse([p for p in editable if p.startswith("tests/")])

    def test_the_safety_system_itself_stays_denied(self):
        editable = [p.replace(os.sep, "/")
                    for p in edit_guard.list_editable_files()]

        for protected in (
            "main.py",
            "commands/command_handlers.py",
            "core/config.py",
            "core/dev_auth.py",
            "ui/ui.py",
        ):
            self.assertNotIn(protected, editable)

        self.assertFalse([p for p in editable if p.startswith("editing/")])

    def test_ordinary_modules_are_still_editable(self):
        # The point is a narrow boundary, not a frozen project.
        editable = [p.replace(os.sep, "/")
                    for p in edit_guard.list_editable_files()]

        for allowed in ("voice/offline_voice.py", "core/tutorial.py",
                        "memory/memory_logic.py"):
            self.assertIn(allowed, editable)

    def test_the_autonomous_set_is_a_subset_of_the_approved_set(self):
        # Anything editable without a human present must also be editable
        # with one; the reverse would be a hole.
        approved = {p.replace(os.sep, "/")
                    for p in edit_guard.list_editable_files()}
        unattended = {p.replace(os.sep, "/")
                      for p in edit_guard.list_autonomous_files()}

        self.assertTrue(unattended <= approved,
                        f"unattended-only: {unattended - approved}")


class ExpiringNoticeTests(unittest.TestCase):
    """A transient condition should not leave a permanent-looking error."""

    def setUp(self):
        self._saved = list(ui._engine.chat_history)
        ui._engine.chat_history.clear()
        self.addCleanup(
            lambda: ui._engine.chat_history.__setitem__(
                slice(None), self._saved)
        )

    def _visible(self):
        now = time.monotonic()
        return [entry[0] for entry in ui._engine.chat_history
                if entry[2] is None or entry[2] > now]

    def test_a_notice_disappears_and_conversation_does_not(self):
        ui.print_framed("a real reply")
        ui.print_framed("microphone unavailable", expires_in=0.4)

        self.assertEqual(len(self._visible()), 2)
        time.sleep(0.6)

        remaining = self._visible()
        self.assertEqual(remaining, ["a real reply"])

    def test_messages_without_a_lifetime_never_expire(self):
        ui.print_framed("permanent")

        self.assertTrue(
            all(entry[2] is None for entry in ui._engine.chat_history))


class IdleCheckInTests(unittest.TestCase):
    """
    Going quiet should be noticed once, not acted on immediately.

    The shutdown at the end of this is real, so the conditions that reach
    it are worth pinning: a mistake here closes a session someone was
    still using.
    """

    def test_idle_is_its_own_sentinel(self):
        # None already means cancelled and "" is a valid empty submission,
        # so neither can stand in for "nobody is there".
        self.assertIsNotNone(ui.IDLE)
        self.assertNotEqual(ui.IDLE, "")
        self.assertIsNot(ui.IDLE, "")

    def test_input_reports_idle_after_the_timeout(self):
        ui._engine.running = True
        ui._engine.current_input = ""

        with mock.patch.object(ui, "get_char", return_value=None):
            self.assertIs(ui.input_framed("YOU >", idle_timeout=0.3), ui.IDLE)

    def test_a_partly_typed_line_is_never_treated_as_absence(self):
        # Someone mid-sentence is present, however long they pause.
        ui._engine.running = True
        outcome = {}

        def compose():
            with mock.patch.object(ui, "get_char", return_value=None):
                outcome["value"] = ui.input_framed(
                    "YOU >", initial_text="mid sentence", idle_timeout=0.2)

        worker = threading.Thread(target=compose, daemon=True)
        worker.start()
        worker.join(timeout=1.2)

        still_waiting = worker.is_alive() and "value" not in outcome

        ui._engine.running = False
        worker.join(timeout=2.0)
        ui._engine.running = True

        self.assertTrue(still_waiting, f"returned {outcome.get('value')!r}")

    def test_the_check_in_line_survives_an_unreachable_model(self):
        # If this raised or hung, the shutdown that depends on it would
        # never happen and the check-in would fail silently.
        with mock.patch.object(assistant_main.requests, "post",
                               side_effect=OSError("no server")):
            line = assistant_main._idle_check_in_line()

        self.assertIn(line, assistant_main._IDLE_FALLBACK_LINES)

    def test_a_rambling_check_in_is_rejected(self):
        reply = {"choices": [{"message": {"content": "x" * 400}}]}
        response = mock.Mock()
        response.json.return_value = reply
        response.raise_for_status.return_value = None

        with mock.patch.object(assistant_main.requests, "post",
                               return_value=response):
            line = assistant_main._idle_check_in_line()

        # Too long to speak before its own timer runs; falls back instead.
        self.assertIn(line, assistant_main._IDLE_FALLBACK_LINES)

    def test_timings_are_bounded(self):
        # The grace period is measured from the end of speech, so it has
        # to be long enough to answer in.
        self.assertGreaterEqual(config.IDLE_CHECKIN_SECONDS, 60)
        self.assertGreaterEqual(config.IDLE_RESPONSE_SECONDS, 15)


class HardwareHonestyTests(unittest.TestCase):
    """
    It confabulated hardware it does not have.

    Asked a nonsense fragment, it reported "the Whisplay HAT is running at
    72% brightness. Ambient light levels are stable at 380 lux. System
    temperature is 41C" -- three precise readings from sensors that do not
    exist, on a Pi that has never been connected. Told it was wrong, it
    restated the claim in softer words instead of correcting it.

    The cause was the core memory opening with the Pi as the project's
    target, which a small model flattens into a present-tense fact.
    """

    def setUp(self):
        self.prompt = assistant_main._stable_system_prompt()

    def test_the_real_runtime_is_stated_before_the_target_hardware(self):
        where = self.prompt.find("Windows desktop PC")
        pi = self.prompt.find("Raspberry Pi 5")

        self.assertGreater(where, -1, "the actual runtime is not stated")
        self.assertGreater(pi, -1)
        self.assertLess(where, pi,
                        "the Pi is mentioned before the real runtime")

    def test_the_pi_is_marked_as_not_yet_obtained(self):
        lowered = self.prompt.lower()

        self.assertTrue(
            any(p in lowered for p in
                ("not yet obtained", "has not been obtained",
                 "not obtained or connected")),
            "nothing says the Pi is unobtained",
        )
        self.assertTrue(
            any(p in lowered for p in
                ("describe a plan", "never a present fact", "intended future")),
            "nothing marks the Pi as a plan rather than a fact",
        )

    def test_it_is_told_it_has_no_sensors(self):
        lowered = self.prompt.lower()

        self.assertTrue(
            "no sensor" in lowered,
            "the prompt never says it has no sensors",
        )

    def test_invented_measurements_are_forbidden_by_example(self):
        # Checked by meaning, not by phrasing. Pinning the exact sentence
        # made the prompt expensive to improve -- the first rewrite for
        # length broke this test without changing what it forbids.
        lowered = self.prompt.lower()

        self.assertTrue(
            "measurement you did not take" in lowered
            or "never invent an observation" in lowered,
            "nothing forbids stating an unmeasured reading",
        )

        # At least one of the actual fabrications stays as a concrete
        # example; a general instruction to be truthful was not enough.
        self.assertTrue(
            any(f in self.prompt for f in ("41C", "72% brightness", "380 lux")),
            "no concrete example of an invented reading",
        )

    def test_self_correction_must_be_plain(self):
        # Rewording an error is not correcting it.
        lowered = self.prompt.lower()

        self.assertIn("i was wrong", lowered)
        self.assertTrue(
            any(p in lowered for p in
                ("rewording the claim is not", "softer language is not",
                 "rewording the original claim is not")),
            "nothing rules out rewording an error instead of conceding it",
        )

    def test_the_earlier_honesty_rules_survived(self):
        lowered = self.prompt.lower()

        self.assertTrue(
            any(p in lowered for p in
                ("claim no feelings", "asserting an inner state is not",
                 "do not claim feelings")),
            "the no-claimed-feelings rule is gone",
        )
        self.assertTrue(
            "declining" in lowered,
            "the guidance on how to decline is gone",
        )


class DeclaredDependencyTests(unittest.TestCase):
    """
    Every third-party import must be declared in a requirements file.

    soundfile was imported by the music player and declared nowhere. It
    worked here only because librosa -- installed by hand for voice
    analysis and never a project dependency -- happened to pull it in.
    The shipped package had no such accident, so its music player would
    have failed on the recipient's machine with a ModuleNotFoundError.

    Transitive luck is not a dependency declaration, and the machine that
    builds a release is the worst place to notice the difference.
    """

    # Modules that ship with Python, or are the project's own packages.
    _LOCAL = {
        "commands", "core", "editing", "hardware", "memory", "project",
        "tests", "ui", "visualizer", "voice", "web", "main", "glitch_icon",
        # hardware/setup_hardware.py imports its sibling by bare name.
        "tdeck",
    }

    # Third-party imports deliberately left undeclared, each with the
    # reason. An entry here is a decision; anything missing from both this
    # list and the requirements files is an accident, which is the whole
    # point of the check.
    #
    # Being wrapped in try/except is NOT sufficient justification on its
    # own -- soundfile was guarded exactly like these and still broke the
    # shipped music player, because the feature it serves is advertised
    # rather than optional. The question is whether the buddy is expected
    # to work without it.
    _OPTIONAL = {
        "pubsub": "provided by meshtastic, declared in requirements-hardware",
        "spotipy": "optional legacy Spotify API path; absence is reported "
                   "to the operator with install instructions",
        "win32com": "optional Windows COM lookup for the Spotify desktop "
                    "app; falls back silently when absent",
    }

    def _project_root(self):
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))

    def _declared(self):
        root = os.path.join(self._project_root(), "setup")
        names = set()

        for entry in os.listdir(root):
            if not entry.startswith("requirements"):
                continue

            with open(os.path.join(root, entry), encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    name = re.split(r"[<>=!\[; ]", line)[0].strip().lower()
                    if name:
                        # pip is case- and separator-insensitive.
                        names.add(name.replace("-", "_"))

        return names

    def _imports(self):
        """Top-level third-party modules imported anywhere in assistant/."""
        import ast

        base = os.path.join(self._project_root(), "assistant")
        found = {}

        for folder, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            for name in files:
                if not name.endswith(".py"):
                    continue

                path = os.path.join(folder, name)
                try:
                    with open(path, encoding="utf-8") as handle:
                        tree = ast.parse(handle.read(), filename=path)
                except (OSError, SyntaxError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        mods = [a.name for a in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        # Relative imports are always local.
                        mods = [node.module] if node.level == 0 and node.module else []
                    else:
                        continue

                    for mod in mods:
                        top = mod.split(".")[0]
                        found.setdefault(top, os.path.relpath(path, base))

        return found

    def test_every_third_party_import_is_declared(self):
        import sys

        stdlib = set(getattr(sys, "stdlib_module_names", ()))
        declared = self._declared()

        # pip distribution names that differ from the imported module.
        aliases = {
            "sherpa_onnx": {"sherpa_onnx", "sherpa_onnx_core"},
            "piper": {"piper_tts"},
            "serial": {"pyserial"},
            "yaml": {"pyyaml"},
            "PIL": {"pillow"},
        }

        undeclared = []

        for module, where in sorted(self._imports().items()):
            if module in stdlib or module in self._LOCAL:
                continue
            if module in self._OPTIONAL:
                continue
            if module.startswith("_"):
                continue

            candidates = aliases.get(module, {module.lower()})

            if not (candidates & declared):
                undeclared.append(f"{module} (imported by {where})")

        self.assertEqual(
            undeclared, [],
            "imported but not in any setup/requirements*.txt -- these would "
            "fail on a clean install",
        )

    def test_the_release_pins_cover_the_same_packages(self):
        # A package can be declared for developers and forgotten in the
        # release pin file, which is what actually reaches the recipient.
        root = os.path.join(self._project_root(), "setup")

        def names(filename):
            out = set()
            with open(os.path.join(root, filename), encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        out.add(re.split(r"[<>=!\[; ]", line)[0].lower())
            return out

        runtime = names("requirements.txt") | names("requirements-voice.txt")
        release = names("requirements-release-windows.txt")

        self.assertEqual(
            sorted(runtime - release), [],
            "declared for development but missing from the release pins",
        )


class PersonaShotsTests(unittest.TestCase):
    """
    Style has to be demonstrated, not just described.

    The shot list was emptied once because the model copied example
    wording verbatim. With no examples a 4B instruct model reverts to its
    tuned register, and every reply became "How may I assist you today?"
    -- the exact phrasing the Voice section rejects. An empty list is
    therefore a regression, not a clean slate.
    """

    def test_examples_exist_at_all(self):
        self.assertTrue(
            persona.PERSONA_SHOTS,
            "no demonstrations left; the model will fall back to the "
            "generic assistant register it was tuned on",
        )

    def test_enough_variety_that_none_becomes_the_formula(self):
        shots = persona.PERSONA_SHOTS
        self.assertGreaterEqual(len(shots) // 2, 4)

        openings = [
            m["content"].split()[0].lower().strip(".,")
            for m in shots if m["role"] == "assistant"
        ]
        # Repeating one opening across most replies is how a catchphrase
        # forms, which is what emptying the list was trying to avoid.
        most_common = max(Counter(openings).values())
        self.assertLessEqual(
            most_common, max(1, len(openings) // 3),
            f"assistant replies start the same way too often: {openings}",
        )

    def test_they_alternate_and_are_well_formed(self):
        shots = persona.PERSONA_SHOTS
        self.assertEqual(len(shots) % 2, 0, "a shot is missing its reply")

        for index, message in enumerate(shots):
            self.assertEqual(message["role"],
                             "user" if index % 2 == 0 else "assistant")
            self.assertTrue(message["content"].strip())

    def test_they_demonstrate_the_honesty_rules(self):
        replies = " ".join(
            m["content"].lower() for m in persona.PERSONA_SHOTS
            if m["role"] == "assistant"
        )
        # Cheaper to show these than to describe them.
        self.assertIn("no sensor", replies)
        self.assertIn("i was wrong", replies)

    def test_no_reply_uses_the_service_desk_register(self):
        banned = ("how may i assist", "how can i assist",
                  "how may i help you today")
        for message in persona.PERSONA_SHOTS:
            if message["role"] != "assistant":
                continue
            lowered = message["content"].lower()
            for phrase in banned:
                self.assertNotIn(phrase, lowered)

    def test_the_shots_reach_the_model(self):
        messages = assistant_main.build_messages("hello")
        rendered = [m.get("content", "") for m in messages]

        for shot in persona.PERSONA_SHOTS:
            self.assertIn(shot["content"], rendered)

    def test_the_prompt_still_leaves_room_to_talk(self):
        # Demonstrations are worth their tokens only while the
        # conversation still fits beside them.
        messages = assistant_main.build_messages("hello")
        text = "\n".join(m.get("content", "") for m in messages)

        # Rough estimate; the real count needs a running server.
        approx_tokens = len(text) // 4
        self.assertLess(approx_tokens, config.CONTEXT_SIZE // 2)


class SpeechPauseTests(unittest.TestCase):
    """
    A full stop and a mid-sentence break are not the same silence.

    Every chunk boundary used to get one pause length. Long sentences are
    split at an arbitrary word boundary to fit the synthesiser, so those
    splits were being given the full sentence pause -- inventing a stop
    the text never had, in the middle of a thought.
    """

    def _timed_gaps(self, text):
        voice = offline_voice.OfflineVoice.__new__(offline_voice.OfflineVoice)
        voice.piper_voice = object()
        voice.speech_syn_config = None

        gaps = []
        previous = [None]

        def fake_play(*args, **kwargs):
            now = time.monotonic()
            if previous[0] is not None:
                gaps.append(now - previous[0])
            previous[0] = now
            return True

        with mock.patch.object(offline_voice.OfflineVoice,
                               "_load_piper", lambda self: None), \
             mock.patch.object(offline_voice.OfflineVoice,
                               "_synthesize_wav_bytes",
                               lambda self, *a, **k: b"x"), \
             mock.patch.object(offline_voice.OfflineVoice,
                               "_play_wav_bytes", fake_play):
            voice.speak(text, lambda: False)

        return gaps

    def test_a_clause_break_is_much_shorter_than_a_full_stop(self):
        self.assertLess(
            config.VOICE_SPEECH_CLAUSE_PAUSE_SECONDS,
            config.VOICE_SPEECH_PAUSE_SECONDS / 3,
        )

    def test_sentence_ends_get_the_full_pause(self):
        gaps = self._timed_gaps("One thing. Another thing. A third.")

        self.assertTrue(gaps)
        for gap in gaps:
            self.assertAlmostEqual(
                gap, config.VOICE_SPEECH_PAUSE_SECONDS, delta=0.25)

    def test_a_split_long_sentence_does_not_gain_a_full_stop(self):
        long_sentence = "we kept going " * 40 + "and then it worked."
        chunks = offline_voice._speech_chunks(long_sentence)

        self.assertGreater(len(chunks), 1, "fixture was not long enough")

        # Only the final chunk is a real sentence end.
        for chunk in chunks[:-1]:
            self.assertFalse(chunk.rstrip().endswith((".", "!", "?")))

        gaps = self._timed_gaps(long_sentence)
        self.assertTrue(gaps)
        for gap in gaps:
            self.assertLess(gap, config.VOICE_SPEECH_PAUSE_SECONDS / 2)

    def test_both_pauses_are_tunable_without_editing_code(self):
        source = inspect.getsource(config)

        self.assertIn("TORMENT_NEXUS_PAUSE_SECONDS", source)
        self.assertIn("TORMENT_NEXUS_CLAUSE_PAUSE", source)


if __name__ == "__main__":
    unittest.main()
