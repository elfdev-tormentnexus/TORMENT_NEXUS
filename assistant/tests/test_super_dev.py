"""Regression checks for the hazard-only two-model Super Dev boundary."""

import os
import tempfile
import unittest
from unittest import mock

from commands import command_handlers
from core import config, dev_auth
from editing import edit_engine, super_dev_engine


class SuperDevAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = dev_auth.SUPER_PASSCODE_FILE
        self.old_iterations = dev_auth.PBKDF2_ITERATIONS
        dev_auth.SUPER_PASSCODE_FILE = os.path.join(self.temp.name, ".super_key")
        dev_auth.PBKDF2_ITERATIONS = 100_000
        dev_auth.reset_attempt_state_for_tests()

    def tearDown(self):
        dev_auth.SUPER_PASSCODE_FILE = self.old_path
        dev_auth.PBKDF2_ITERATIONS = self.old_iterations
        dev_auth.reset_attempt_state_for_tests()
        self.temp.cleanup()

    def test_super_key_is_a_separate_salted_local_verifier(self):
        secret = "246813579"
        dev_auth.enroll_super(secret, secret)

        with open(dev_auth.SUPER_PASSCODE_FILE, encoding="utf-8") as source:
            saved = source.read()

        self.assertNotIn(secret, saved)
        self.assertTrue(dev_auth.verify_super(secret))
        self.assertFalse(dev_auth.verify_super("975318642"))


class SuperDevWorkerBoundaryTests(unittest.TestCase):
    def test_worker_must_be_local_and_authenticated(self):
        with mock.patch.object(
            super_dev_engine, "SUPER_DEV_WORKER_URL", "https://example.com:8093"
        ), mock.patch.object(super_dev_engine, "SUPER_DEV_WORKER_HEADERS", {"Authorization": "Bearer x"}):
            ready, message = super_dev_engine.worker_status()

        self.assertFalse(ready)
        self.assertIn("loopback", message)

    def test_super_session_refuses_wrong_model_profile_before_any_network_call(self):
        with mock.patch.object(
            super_dev_engine, "MODEL_ROLE", config.MODEL_ROLE_DIRECTOR
        ), mock.patch.object(super_dev_engine, "worker_status") as worker:
            applied, message = super_dev_engine.run_session()

        self.assertFalse(applied)
        self.assertIn("dedicated super-dev launcher", message)
        worker.assert_not_called()


class SuperDevCommandTests(unittest.TestCase):
    def setUp(self):
        self.old_mode = command_handlers.SUPER_DEV_MODE
        self.old_expires = command_handlers.SUPER_DEV_MODE_EXPIRES_AT
        command_handlers.SUPER_DEV_MODE = False
        command_handlers.SUPER_DEV_MODE_EXPIRES_AT = 0.0

    def tearDown(self):
        command_handlers.SUPER_DEV_MODE = self.old_mode
        command_handlers.SUPER_DEV_MODE_EXPIRES_AT = self.old_expires

    def test_unlock_runs_one_session_and_marks_only_a_verified_patch_for_reload(self):
        with mock.patch.object(command_handlers, "is_experimental_mode", return_value=True), \
             mock.patch.object(command_handlers, "MODEL_ROLE", config.MODEL_ROLE_SUPER_DEV), \
             mock.patch.object(dev_auth, "unlock_super_interactive", return_value=(True, "key accepted")), \
             mock.patch.object(super_dev_engine, "run_session", return_value=(True, "verified")) as session, \
             mock.patch.object(edit_engine, "mark_restart_pending") as restart:
            reply = command_handlers.handle_super_dev_mode("super dev mode")

        session.assert_called_once_with()
        restart.assert_called_once_with()
        self.assertIn("verified", reply)
        self.assertTrue(command_handlers.SUPER_DEV_MODE)

    def test_inline_super_key_is_refused(self):
        reply = command_handlers.handle_super_dev_mode("super dev mode 246813579")
        self.assertIn("masked numeric prompt", reply)


class SuperDevSessionLoopTests(unittest.TestCase):
    """The unattended session must end on its own and gate every patch.

    An unattended loop has two failure modes a reader cannot check by
    inspection: it never stops, or it stops gating. Both are held here.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(super_dev_engine, "MODEL_ROLE",
                              config.MODEL_ROLE_SUPER_DEV),
            mock.patch.object(super_dev_engine, "STATE_FILE",
                              os.path.join(self.temp.name, "absent.json")),
            mock.patch.object(super_dev_engine, "worker_status",
                              return_value=(True, "ready")),
            mock.patch.object(super_dev_engine, "_log"),
            mock.patch.object(super_dev_engine.ui, "set_status"),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    @staticmethod
    def _candidate(index):
        return {"file": f"file_{index}.py", "change": f"change {index}"}

    @staticmethod
    def _accept(suggestion):
        """Stand in for a patch that really wrote and cleared the gate.

        The double has to move the write counter, because the session refuses
        to count a success that did not. A plain `return True, ...` here is
        indistinguishable from the no-op bug the guard watches for.
        """
        super_dev_engine._patches_written += 1
        return True, suggestion["file"]

    @classmethod
    def _accept_taking(cls, clock, seconds):
        """The same double, but one that costs time on the fake clock."""
        def accept(suggestion):
            clock.now += seconds
            return cls._accept(suggestion)
        return accept

    def test_session_retains_more_than_one_patch(self):
        rounds = [([self._candidate(i)], None) for i in range(5)]
        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=rounds), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=self._accept) as attempt:
            applied, report = super_dev_engine.run_session(limit=3)

        self.assertTrue(applied)
        self.assertEqual(attempt.call_count, 3)
        self.assertIn("retained 3 patches", report)
        self.assertIn("file_0.py", report)
        self.assertIn("file_2.py", report)

    def test_session_stops_at_its_limit_even_when_work_remains(self):
        with mock.patch.object(
                super_dev_engine.suggestion_engine, "generate",
                side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=self._accept) as attempt:
            applied, report = super_dev_engine.run_session(limit=2)

        self.assertTrue(applied)
        self.assertEqual(attempt.call_count, 2)
        self.assertIn("limit of 2 was reached", report)

    def test_session_ends_when_the_time_window_closes(self):
        # The clock is the only bound in the default configuration, so it has
        # to hold on its own with no patch limit set at all. The fake clock
        # moves only when a patch does, so this does not depend on how many
        # times the loop happens to poll it.
        clock = _FakeClock()
        with mock.patch.object(super_dev_engine.time, "monotonic", clock), \
             mock.patch.object(
                 super_dev_engine.suggestion_engine, "generate",
                 side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=self._accept_taking(clock, 3.0)) as attempt:
            applied, report = super_dev_engine.run_session(max_seconds=10)

        self.assertTrue(applied)
        self.assertIn("session window closed", report)
        # Four patches fit inside ten seconds at three seconds each; the
        # fifth is refused because the window had already closed.
        self.assertEqual(attempt.call_count, 4)

    def test_success_without_a_write_halts_the_session(self):
        # The ported run_observed_serial() guard. A _try_patch that claims
        # success without incrementing the write counter must stop the run,
        # not be counted -- with no patch cap it would otherwise spin.
        with mock.patch.object(
                super_dev_engine.suggestion_engine, "generate",
                side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_patches_written", 7), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               return_value=(True, "claimed")) as attempt:
            applied, report = super_dev_engine.run_session(max_seconds=600)

        self.assertFalse(applied)
        self.assertEqual(attempt.call_count, 1)
        self.assertIn("without writing", report)

    def test_a_real_write_increments_the_counter_the_guard_reads(self):
        # The guard above is only meaningful if the success path really does
        # move the counter. Pin that here so the two cannot drift apart.
        source = "value = 1\n"
        with mock.patch.object(super_dev_engine.edit_guard, "locate",
                               return_value="target.py"), \
             mock.patch.object(super_dev_engine.edit_guard, "read",
                               return_value=source), \
             mock.patch.object(super_dev_engine.edit_generator, "generate_edit",
                               return_value=({"find": "1", "replace": "2",
                                              "explanation": "bump"}, None)), \
             mock.patch.object(super_dev_engine.edit_guard, "check_syntax",
                               return_value=None), \
             mock.patch.object(super_dev_engine.edit_guard,
                               "autonomous_change_problem", return_value=None), \
             mock.patch.object(super_dev_engine.edit_guard, "backup",
                               return_value="backup.py"), \
             mock.patch.object(super_dev_engine.edit_guard, "write"), \
             mock.patch.object(super_dev_engine, "_write_state"), \
             mock.patch.object(super_dev_engine, "_clear_state"), \
             mock.patch.object(super_dev_engine.self_heal_state,
                               "validate_restart", return_value=(True, "")):
            before = super_dev_engine._patches_written
            accepted, _ = super_dev_engine._try_patch(self._candidate(0))
            after = super_dev_engine._patches_written

        self.assertTrue(accepted)
        self.assertEqual(after, before + 1)

    def test_default_session_has_no_patch_cap(self):
        # The old build stopped after a fixed number of patches. Twenty here
        # is well past any such cap; only the clock ends this run.
        clock = _FakeClock()
        with mock.patch.object(super_dev_engine.time, "monotonic", clock), \
             mock.patch.object(
                 super_dev_engine.suggestion_engine, "generate",
                 side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=self._accept_taking(clock, 1.0)) as attempt:
            applied, report = super_dev_engine.run_session(max_seconds=20)

        self.assertTrue(applied)
        self.assertEqual(attempt.call_count, 20)
        self.assertIn("session window closed", report)
        self.assertNotIn("patch limit", report)

    def test_a_rejected_candidate_is_never_retried_so_the_loop_ends(self):
        # The planner keeps proposing the same two things; the gates keep
        # refusing them. Without the attempted-set this runs until the limit.
        same = [self._candidate(1), self._candidate(2)]
        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               return_value=(same, None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               return_value=(False, "gate refused")) as attempt:
            applied, report = super_dev_engine.run_session(limit=20)

        self.assertFalse(applied)
        self.assertEqual(attempt.call_count, 2)
        self.assertIn("No files changed", report)

    def test_every_patch_is_gated_individually_not_batched(self):
        # _try_patch is the whole gate set. One call per retained patch means
        # the gates ran per patch; a batched implementation would call it once.
        rounds = [([self._candidate(i)], None) for i in range(3)]
        seen = []

        def gate(suggestion):
            seen.append(suggestion["file"])
            return self._accept(suggestion)

        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=rounds), \
             mock.patch.object(super_dev_engine, "_try_patch", side_effect=gate):
            super_dev_engine.run_session(limit=3)

        self.assertEqual(seen, ["file_0.py", "file_1.py", "file_2.py"])

    def test_planner_failure_keeps_the_patches_already_verified(self):
        rounds = [([self._candidate(0)], None), ([], "planner unreachable")]
        with mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=rounds), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=self._accept):
            applied, report = super_dev_engine.run_session(limit=5)

        self.assertTrue(applied)
        self.assertIn("retained 1 patch", report)
        self.assertIn("planner unreachable", report)

    def test_window_defaults_to_the_configured_ceiling(self):
        # No max_seconds argument: the session must pick up the config value.
        clock = _FakeClock()
        with mock.patch.object(super_dev_engine,
                               "SUPER_DEV_SESSION_MAX_SECONDS", 10), \
             mock.patch.object(super_dev_engine.time, "monotonic", clock), \
             mock.patch.object(super_dev_engine.suggestion_engine, "generate",
                               side_effect=lambda **kw: ([self._candidate(mock_counter())], None)), \
             mock.patch.object(super_dev_engine, "_try_patch",
                               side_effect=self._accept_taking(clock, 4.0)) as attempt:
            applied, report = super_dev_engine.run_session()

        self.assertTrue(applied)
        self.assertIn("session window closed", report)
        self.assertEqual(attempt.call_count, 3)


_counter = {"n": 0}


def mock_counter():
    _counter["n"] += 1
    return _counter["n"]


class _FakeClock:
    """A monotonic stand-in that advances only when the test says so.

    The session polls the clock an unspecified number of times per round, so
    a scripted list of readings breaks whenever that polling changes. Letting
    the patch double push the clock forward instead models the real cost --
    a patch takes time, checking the time does not -- and keeps these tests
    insensitive to the loop's internals.
    """

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


if __name__ == "__main__":
    unittest.main()
