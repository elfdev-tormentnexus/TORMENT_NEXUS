"""Privacy and validation boundaries for operator-owned local songs."""

import json
import os
import tempfile
import unittest
from unittest import mock

from commands import command_handlers
from voice import local_song_loader
from voice import offline_voice
from voice import session as voice_session


def _definition(**changes):
    value = {
        "format_version": 1,
        "command": "sing private test",
        "name": "Private Test",
        "score": [
            [None, None, 6],
            ["sea", 60, 6],
        ],
        "eighth_seconds": 0.2,
        "harmony": {"C": [48, 55, 60, 64]},
        "chords": ["C", "C"],
        "intro_melody": [[60, 6]],
        "cache_filename": "private_test_v1.wav",
        "accompaniment_gain": 0.24,
        "vocal_semitones": -12,
    }
    value.update(changes)
    return value


class LocalSongLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def _write(self, name="private_test.json", definition=None):
        path = os.path.join(self.temporary.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(_definition() if definition is None else definition, handle)
        return path

    def test_missing_private_directory_is_harmless(self):
        missing = os.path.join(self.temporary.name, "missing")
        result = local_song_loader.load_local_songs(
            offline_voice.Song,
            directory=missing,
        )

        self.assertEqual(result.entries, ())
        self.assertEqual(result.issues, ())

    def test_valid_data_builds_song_and_pins_cache_below_private_folder(self):
        self._write()
        result = local_song_loader.load_local_songs(
            offline_voice.Song,
            directory=self.temporary.name,
        )

        self.assertEqual(result.issues, ())
        self.assertEqual(len(result.entries), 1)
        entry = result.entries[0]
        self.assertEqual(entry.command, "sing private test")
        self.assertIsInstance(entry.song, offline_voice.Song)
        self.assertEqual(entry.song.vocal_semitones, -12.0)
        self.assertEqual(entry.song.measure_units, 6)
        self.assertEqual(
            entry.song.cache_path,
            os.path.join(
                os.path.realpath(self.temporary.name),
                "cache",
                "private_test_v1.wav",
            ),
        )

    def test_four_four_definition_uses_eight_eighth_units_per_measure(self):
        definition = _definition(
            score=[[None, None, 8], ["sea", 60, 8]],
            chords=["C", "C"],
            intro_melody=[[60, 8]],
            measure_units=8,
        )
        self._write(definition=definition)
        result = local_song_loader.load_local_songs(
            offline_voice.Song,
            directory=self.temporary.name,
        )

        self.assertEqual(result.issues, ())
        self.assertEqual(result.entries[0].song.measure_units, 8)

    def test_unknown_field_and_path_like_cache_are_rejected_per_file(self):
        invalid = _definition(cache_filename="..\\published.wav", surprise=True)
        self._write(definition=invalid)
        result = local_song_loader.load_local_songs(
            offline_voice.Song,
            directory=self.temporary.name,
        )

        self.assertEqual(result.entries, ())
        self.assertEqual(len(result.issues), 1)
        self.assertIn("unknown fields", result.issues[0].reason)

    def test_intro_cannot_overlap_the_private_vocal(self):
        invalid = _definition(intro_melody=[[60, 12]])
        self._write(definition=invalid)
        result = local_song_loader.load_local_songs(
            offline_voice.Song,
            directory=self.temporary.name,
        )

        self.assertEqual(result.entries, ())
        self.assertIn("leading silence", result.issues[0].reason)

    def test_local_command_queues_validated_song_object(self):
        self._write()
        voice_session.clear_start_request()
        voice_session.clear_song_request()
        self.addCleanup(voice_session.clear_start_request)
        self.addCleanup(voice_session.clear_song_request)

        with mock.patch.object(command_handlers, "COMMANDS", []):
            result = command_handlers._register_local_song_commands(
                self.temporary.name
            )
            with mock.patch.object(
                offline_voice,
                "setup_report",
                return_value=(True, "ready"),
            ):
                reply = command_handlers.try_handle_command("sing private test")

            self.assertEqual(len(result.entries), 1)
            self.assertTrue(voice_session.is_silent_reply(reply))
            self.assertTrue(voice_session.consume_start_request())
            queued = voice_session.consume_song_request()
            self.assertIsInstance(queued, offline_voice.Song)
            self.assertEqual(queued.name, "Private Test")

    def test_existing_command_cannot_be_shadowed(self):
        self._write(definition=_definition(command="sing daisy bell"))
        original = list(command_handlers.COMMANDS)

        with mock.patch.object(command_handlers, "COMMANDS", original):
            before = len(command_handlers.COMMANDS)
            command_handlers._register_local_song_commands(self.temporary.name)
            self.assertEqual(len(command_handlers.COMMANDS), before)


if __name__ == "__main__":
    unittest.main()
