from datetime import datetime
import os
import shutil
import tempfile
import unittest
from unittest import mock

from core import first_run
from core import system_awareness


class FirstRunDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="torment-first-run-test-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.state = os.path.join(self.folder, "ack.json")

    def test_declining_starts_nothing_and_saves_nothing(self):
        output = []
        with mock.patch.object(first_run, "STATE_FILE", self.state):
            accepted = first_run.ensure_acknowledged(
                input_fn=lambda _prompt: "no",
                output_fn=output.append,
            )
        self.assertFalse(accepted)
        self.assertFalse(os.path.exists(self.state))
        self.assertIn("abliterated", "\n".join(output).lower())
        self.assertIn("nothing was started", "\n".join(output).lower())

    def test_exact_acknowledgement_is_persisted(self):
        with mock.patch.object(first_run, "STATE_FILE", self.state):
            self.assertTrue(first_run.ensure_acknowledged(
                input_fn=lambda _prompt: first_run.ACCEPT_TEXT,
                output_fn=lambda _line: None,
            ))
            self.assertTrue(first_run.acknowledged())
            # The saved decision prevents a second prompt.
            self.assertTrue(first_run.ensure_acknowledged(
                input_fn=lambda _prompt: self.fail("prompted twice"),
                output_fn=lambda _line: None,
            ))

    def test_notice_names_behavior_tools_privacy_and_personification(self):
        lowered = first_run.NOTICE.lower()
        for required in (
            "abliterated",
            "refusal",
            "administrator",
            "microphone is off",
            "activity awareness is off",
            "cloud escalation",
            "not conscious",
            "backups",
        ):
            self.assertIn(required, lowered)


class ActivityConsentTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="torment-activity-test-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.log = os.path.join(self.folder, "activity.jsonl")
        self.preference = os.path.join(self.folder, "consent.json")

    def _awareness(self):
        return system_awareness.SystemAwareness(
            sample_seconds=20,
            store_path=self.log,
            retention_days=14,
            enabled=False,
            preference_path=self.preference,
        )

    def test_fresh_install_is_off_and_does_not_load_a_legacy_log(self):
        with open(self.log, "w", encoding="utf-8") as handle:
            handle.write('{"t":1,"a":"private.exe","w":"private title"}\n')
        awareness = self._awareness()
        self.assertFalse(awareness.enabled)
        self.assertEqual(awareness.load(), 0)
        self.assertEqual(awareness.snapshots(), [])

    def test_opt_in_persists_and_off_deletes_every_observation(self):
        awareness = self._awareness()
        awareness.set_enabled(True)
        awareness._record(system_awareness.Snapshot(
            taken_at=datetime.now().astimezone(),
            app="editor.exe",
            title="private document",
            idle_seconds=1,
        ))
        self.assertTrue(os.path.isfile(self.log))

        restarted = self._awareness()
        self.assertTrue(restarted.enabled)
        self.assertGreater(restarted.load(), 0)

        restarted.set_enabled(False)
        self.assertFalse(restarted.enabled)
        self.assertFalse(os.path.exists(self.log))
        self.assertEqual(restarted.snapshots(), [])

        final = self._awareness()
        self.assertFalse(final.enabled)


if __name__ == "__main__":
    unittest.main()

