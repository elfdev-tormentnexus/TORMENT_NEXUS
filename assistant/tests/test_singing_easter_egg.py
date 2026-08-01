"""Focused coverage for the fixed and bounded offline machine songs."""

import json
import os
import tempfile
import unittest
from unittest import mock

import main as assistant_main
from commands import command_handlers
from commands import natural_command
from core import config
from voice import offline_voice
from voice import freestyle_song
from voice import session as voice_session


class JosephineScoreTests(unittest.TestCase):
    def test_public_domain_chorus_matches_the_transcribed_32_bar_shape(self):
        expected = (
            ((67, 2), (64, 2), (65, 2)),
            ((67, 2), (69, 2), (71, 2)),
            ((72, 2), (71, 2), (72, 2)),
            ((76, 2), (74, 2), (72, 2)),
            ((71, 2), (None, 2), (74, 2)),
            ((65, 6),),
            ((71, 2), (None, 2), (74, 2)),
            ((65, 6),),
            ((65, 2), (62, 2), (64, 2)),
            ((65, 2), (67, 2), (69, 2)),
            ((71, 2), (70, 2), (71, 2)),
            ((74, 2), (72, 2), (71, 2)),
            ((69, 2), (None, 2), (72, 2)),
            ((64, 6),),
            ((69, 2), (None, 2), (72, 2)),
            ((64, 6),),
            ((67, 2), (None, 4)),
            ((72, 2), (None, 2), (69, 2)),
            ((71, 2), (74, 2), (71, 2)),
            ((69, 4), (68, 2)),
            ((67, 2), (None, 4)),
            ((72, 2), (None, 2), (69, 2)),
            ((71, 2), (74, 2), (71, 2)),
            ((69, 4), (68, 2)),
            ((67, 2), (64, 2), (65, 2)),
            ((67, 2), (69, 2), (71, 2)),
            ((72, 2), (71, 2), (72, 2)),
            ((76, 2), (74, 2), (72, 2)),
            ((71, 2), (None, 2), (69, 2)),
            ((67, 2), (None, 2), (76, 2)),
            ((72, 6),),
            ((72, 2), (None, 4)),
        )
        actual = []
        bar = []
        units = 0

        for _text, note, duration in offline_voice.COME_JOSEPHINE_CHORUS:
            remaining = duration

            while remaining:
                piece = min(remaining, 6 - units)
                bar.append((note, piece))
                units += piece
                remaining -= piece

                if units == 6:
                    actual.append(tuple(bar))
                    bar = []
                    units = 0

        self.assertFalse(bar)
        self.assertEqual(tuple(actual), expected)

    def test_answer_keeps_every_note_and_duration_but_changes_the_words(self):
        chorus_shape = tuple(
            (note, duration)
            for _text, note, duration
            in offline_voice.COME_JOSEPHINE_CHORUS
        )
        answer_shape = tuple(
            (note, duration)
            for _text, note, duration
            in offline_voice.JOSEPHINE_ANSWERING_VERSE
        )
        answer_words = " ".join(
            text
            for text, _note, _duration
            in offline_voice.JOSEPHINE_ANSWERING_VERSE
            if text
        )

        self.assertEqual(answer_shape, chorus_shape)
        self.assertIn("hum ing ma sheen", answer_words)
        self.assertIn("sig null is on fire", answer_words)
        self.assertIn("don't let go", answer_words)

    def test_intro_and_accompaniment_cover_the_complete_performance(self):
        performance_units = sum(
            duration
            for _text, _note, duration
            in offline_voice.COME_JOSEPHINE_PERFORMANCE
        )

        self.assertEqual(offline_voice.JOSEPHINE_INTRO_MEASURES, 32)
        self.assertEqual(performance_units % 6, 0)
        self.assertEqual(
            len(offline_voice.JOSEPHINE_PERFORMANCE_CHORDS),
            performance_units // 6,
        )
        self.assertEqual(
            len(offline_voice.JOSEPHINE_CHORD_PROGRESSION),
            32,
        )

    def test_josephine_has_an_independent_cache_and_registry_identity(self):
        song = offline_voice.COME_JOSEPHINE_SONG

        self.assertIs(
            offline_voice.song_by_key("come josephine"),
            song,
        )
        self.assertIs(
            offline_voice.song_by_key(
                "Come Josephine in my flying machine"
            ),
            song,
        )
        self.assertNotEqual(song.cache_path, offline_voice.DAISY_SONG.cache_path)
        self.assertEqual(song.cache_path, config.VOICE_JOSEPHINE_CACHE)

    def test_josephine_lowers_only_the_vocal_carrier_by_one_octave(self):
        song = offline_voice.COME_JOSEPHINE_SONG
        first_note = next(
            note for text, note, _units in song.score if text and note is not None
        )

        self.assertEqual(song.vocal_semitones, -12.0)
        self.assertEqual(offline_voice.DAISY_SONG.vocal_semitones, 0.0)
        self.assertEqual(first_note, 67, "the transcribed score was changed")
        self.assertAlmostEqual(
            offline_voice._midi_frequency(first_note + song.vocal_semitones),
            offline_voice._midi_frequency(first_note) / 2.0,
            places=7,
        )
        self.assertIn("v2_vocal-minus12", song.cache_path)

    def test_public_method_uses_the_shared_player(self):
        voice = offline_voice.OfflineVoice.__new__(offline_voice.OfflineVoice)
        cancelled = lambda: False
        phase_changed = mock.Mock()

        with mock.patch.object(
            offline_voice.OfflineVoice,
            "sing",
            return_value=True,
        ) as sing:
            self.assertTrue(
                voice.sing_come_josephine(cancelled, phase_changed)
            )

        sing.assert_called_once_with(
            offline_voice.COME_JOSEPHINE_SONG,
            cancelled,
            phase_changed,
        )


class JosephineDispatchTests(unittest.TestCase):
    def setUp(self):
        voice_session.clear_start_request()
        voice_session.clear_song_request()

    def tearDown(self):
        voice_session.clear_start_request()
        voice_session.clear_song_request()

    def test_exact_command_queues_josephine_and_audio_mode(self):
        with mock.patch.object(
            offline_voice,
            "setup_report",
            return_value=(True, "ready"),
        ):
            reply = command_handlers.handle_sing_come_josephine(
                "sing come josephine"
            )

        self.assertIn("original verse", reply.lower())
        self.assertTrue(voice_session.consume_start_request())
        self.assertEqual(
            voice_session.consume_song_request(),
            "come_josephine",
        )

    def test_natural_wording_routes_without_a_model_call(self):
        result = natural_command.interpret(
            "Could you perform the song Come Josephine in my flying machine?",
            command_handlers.command_catalog(),
            dev_mode=False,
        )

        self.assertEqual(result["command"], "sing come josephine")
        self.assertEqual(result["source"], "rule")

    def test_audio_mode_phrase_router_keeps_both_fixed_songs(self):
        self.assertEqual(
            assistant_main._song_request_phrase("sing Come Josephine"),
            "come_josephine",
        )
        self.assertEqual(
            assistant_main._song_request_phrase("please play Daisy Bell"),
            "daisy_bell",
        )
        self.assertTrue(
            assistant_main._daisy_request_phrase("perform Daisy Bell")
        )
        self.assertIsNone(
            assistant_main._song_request_phrase("Josephine is a nice name")
        )

    def test_main_uses_the_real_song_name_for_status_and_indicator(self):
        input_state = mock.Mock()
        input_state.poll.return_value = False
        input_state.consume_playback_stop.return_value = False
        voice = mock.Mock()

        def perform(song, cancelled, phase_changed):
            self.assertIs(song, offline_voice.COME_JOSEPHINE_SONG)
            self.assertFalse(cancelled())
            phase_changed("building Come Josephine voice")
            phase_changed("singing Come Josephine")
            return True

        voice.sing.side_effect = perform

        with mock.patch.object(assistant_main.ui, "set_generating"), \
                mock.patch.object(assistant_main.ui, "set_status") as status, \
                mock.patch.object(
                    assistant_main.ui,
                    "set_voice_speaking",
                ) as speaking, \
                mock.patch.object(
                    assistant_main.ui,
                    "finish_activity",
                ) as finish, \
                mock.patch.object(assistant_main.ui, "print_framed"):
            self.assertTrue(
                assistant_main._sing_song(
                    voice,
                    input_state,
                    "come_josephine",
                )
            )

        status.assert_any_call("preparing Come Josephine")
        status.assert_any_call("singing Come Josephine")
        speaking.assert_any_call(True)
        finish.assert_called_once_with("Come Josephine complete")

    def test_failed_audio_startup_discards_the_queued_song(self):
        voice_session.request_song("come_josephine")

        with mock.patch.object(assistant_main, "_startup_voice", None), \
                mock.patch.object(
                    assistant_main,
                    "_startup_voice_error",
                    RuntimeError("device disappeared"),
                ), \
                mock.patch.object(assistant_main.ui, "set_voice_mode"), \
                mock.patch.object(assistant_main.ui, "begin_input"), \
                mock.patch.object(assistant_main.ui, "set_generating"), \
                mock.patch.object(assistant_main.ui, "set_status"), \
                mock.patch.object(assistant_main.ui, "finish_activity"), \
                mock.patch.object(assistant_main.ui, "print_framed"):
            assistant_main._voice_mode_loop()

        self.assertIsNone(voice_session.consume_song_request())


class FreestyleIntegrationTests(unittest.TestCase):
    def setUp(self):
        voice_session.clear_start_request()
        voice_session.clear_song_request()

    def tearDown(self):
        voice_session.clear_start_request()
        voice_session.clear_song_request()

    def _draft(self, tune_key="daisy_bell", title="Small Signal"):
        count = offline_voice.freestyle_slot_counts()[tune_key]
        return freestyle_song.FreestyleDraft(
            tune_key=tune_key,
            title=title,
            words=("la",) * count,
        )

    def test_registry_offers_only_fixed_vocal_slot_counts(self):
        self.assertEqual(
            offline_voice.freestyle_slot_counts(),
            {"daisy_bell": 50, "come_josephine": 69},
        )

    def test_draft_replaces_words_without_changing_notes_or_timing(self):
        draft = self._draft("come_josephine")
        song = offline_voice.freestyle_song_from_draft(draft)
        template = offline_voice.COME_JOSEPHINE_CHORUS
        rewritten = song.score[1:1 + len(template)]

        self.assertEqual(
            [(note, units) for _text, note, units in rewritten],
            [(note, units) for _text, note, units in template],
        )
        self.assertEqual(
            [text for text, _note, _units in rewritten if text],
            list(draft.words),
        )
        self.assertEqual(
            len(song.chords),
            sum(units for _text, _note, units in song.score) // 6,
        )
        self.assertEqual(
            song.vocal_semitones,
            offline_voice.COME_JOSEPHINE_SONG.vocal_semitones,
        )

    def test_fake_transport_to_fixed_score_is_a_complete_closed_path(self):
        count = offline_voice.freestyle_slot_counts()["daisy_bell"]
        reply = json.dumps(
            {
                "tune": "daisy_bell",
                "title": "One Clear Line",
                "words": ["la"] * count,
            }
        )
        draft = freestyle_song.generate(
            "the moon",
            offline_voice.freestyle_slot_counts(),
            transport=lambda _request: reply,
        )
        song = offline_voice.freestyle_song_from_draft(draft)

        self.assertEqual(song.name, "Freestyle: One Clear Line")
        rewritten = song.score[1:1 + len(offline_voice.DAISY_CHORUS)]
        self.assertEqual(
            [(note, units) for _text, note, units in rewritten],
            [
                (note, units)
                for _text, note, units in offline_voice.DAISY_CHORUS
            ],
        )

    def test_forged_draft_is_rejected_again_at_the_audio_boundary(self):
        forged = freestyle_song.FreestyleDraft(
            tune_key="daisy_bell",
            title="<stage direction>",
            words=("la",) * 50,
        )

        with self.assertRaises(freestyle_song.FreestyleRejectedError):
            offline_voice.freestyle_song_from_draft(forged)

    def test_freestyle_cache_identity_is_stable_and_lyric_bound(self):
        first = offline_voice.freestyle_song_from_draft(self._draft())
        same = offline_voice.freestyle_song_from_draft(self._draft())
        changed = offline_voice.freestyle_song_from_draft(
            self._draft(title="Other Signal")
        )

        self.assertEqual(first.cache_path, same.cache_path)
        self.assertNotEqual(first.cache_path, changed.cache_path)
        self.assertNotEqual(first.cache_path, offline_voice.DAISY_SONG.cache_path)

    def test_freestyle_cache_pruning_is_bounded_and_preserves_fixed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            generated = []

            for index in range(5):
                path = os.path.join(folder, f"song_freestyle_{index}.wav")

                with open(path, "wb") as handle:
                    handle.write(b"cache")

                os.utime(path, (index + 1, index + 1))
                generated.append(path)

            fixed = os.path.join(folder, "daisy_bell_machine.wav")

            with open(fixed, "wb") as handle:
                handle.write(b"fixed")

            protected = generated[0]
            offline_voice._prune_freestyle_caches(protected, limit=2)
            remaining = {
                name
                for name in os.listdir(folder)
                if "_freestyle_" in name
            }

            self.assertEqual(
                remaining,
                {os.path.basename(protected), os.path.basename(generated[-1])},
            )
            self.assertTrue(os.path.isfile(fixed))

    def test_command_queues_only_the_validated_fixed_score(self):
        draft = self._draft("come_josephine")

        with mock.patch.object(
            offline_voice,
            "setup_report",
            return_value=(True, "ready"),
        ), mock.patch.object(
            freestyle_song,
            "generate",
            return_value=draft,
        ) as generate:
            reply = command_handlers.handle_sing_what_you_want(
                "sing what you want about the night sky"
            )

        self.assertTrue(voice_session.is_silent_reply(reply))
        self.assertIn("notes and timing remain fixed", reply)
        self.assertTrue(voice_session.consume_start_request())
        queued = voice_session.consume_song_request()
        self.assertIsInstance(queued, offline_voice.Song)
        self.assertEqual(queued.name, "Freestyle: Small Signal")
        generate.assert_called_once()
        self.assertEqual(generate.call_args.args[0], "the night sky")

    def test_failed_validation_never_queues_audio(self):
        with mock.patch.object(
            offline_voice,
            "setup_report",
            return_value=(True, "ready"),
        ), mock.patch.object(
            freestyle_song,
            "generate",
            side_effect=freestyle_song.FreestyleRejectedError("wrong count"),
        ):
            reply = command_handlers.handle_sing_what_you_want(
                "sing what you want"
            )

        self.assertIn("nothing was queued", reply)
        self.assertFalse(voice_session.consume_start_request())
        self.assertIsNone(voice_session.consume_song_request())

    def test_natural_freestyle_wording_preserves_the_subject(self):
        result = natural_command.interpret(
            "Could you sing what you want about the cold moon?",
            command_handlers.command_catalog(),
            dev_mode=False,
        )

        self.assertEqual(
            result["command"],
            "sing what you want about the cold moon",
        )
        self.assertEqual(result["source"], "rule")

    def test_local_transport_returns_only_the_model_message(self):
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": '{"tune":"daisy_bell"}'}}]
        }

        with mock.patch.object(
            command_handlers._FREESTYLE_HTTP,
            "post",
            return_value=response,
        ) as post:
            content = command_handlers._freestyle_song_transport("request")

        self.assertEqual(content, '{"tune":"daisy_bell"}')
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(
            post.call_args.args[0],
            config.SERVER_URL + "/v1/chat/completions",
        )
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertFalse(command_handlers._FREESTYLE_HTTP.trust_env)
        request_payload = post.call_args.kwargs["json"]
        self.assertEqual(request_payload["max_tokens"], 1_600)
        branches = request_payload["json_schema"]["oneOf"]
        exact_counts = {
            branch["properties"]["tune"]["const"]:
            branch["properties"]["words"]["minItems"]
            for branch in branches
        }
        self.assertEqual(
            exact_counts,
            {"daisy_bell": 50, "come_josephine": 69},
        )
        self.assertTrue(all(
            branch["properties"]["words"]["minItems"]
            == branch["properties"]["words"]["maxItems"]
            for branch in branches
        ))

    def test_freestyle_transport_refuses_non_loopback_and_redirects(self):
        with mock.patch.object(
            command_handlers,
            "SERVER_URL",
            "https://example.com:8080",
        ), mock.patch.object(
            command_handlers._FREESTYLE_HTTP,
            "post",
        ) as post:
            with self.assertRaisesRegex(RuntimeError, "loopback-only"):
                command_handlers._freestyle_song_transport("request")

        post.assert_not_called()

        redirect = mock.Mock(status_code=302)

        with mock.patch.object(
            command_handlers._FREESTYLE_HTTP,
            "post",
            return_value=redirect,
        ):
            with self.assertRaisesRegex(RuntimeError, "redirect"):
                command_handlers._freestyle_song_transport("request")


if __name__ == "__main__":
    unittest.main()
