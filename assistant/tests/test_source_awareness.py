"""Reading yourself is a different permission from rewriting yourself.

The module under test exists because this build confabulates about its own
work. Asked what it had done to the vector panel, it described tooltips
that appear on hover, in a terminal that has no hover. Sampled three
times on the same opening, one reply in three claimed ownership of work
that did not exist, and the fork was a single token wide -- " working"
against " glad" -- five tokens in.

So these hold two boundaries that are easy to blur into each other:

  * edit_guard.DENIED_FILES stops files being *rewritten*. Every one of
    them must stay *readable*, or the grounding is missing exactly the
    modules a question about this program is most likely to be about.
  * Containment is not negotiable in either direction. Whatever escape
    edit_guard.resolve() refuses, resolve_for_read() must refuse too,
    because reading is duplicated rather than delegated and duplicated
    code drifts.

And two things that are only knowable by measuring: the manifest's cost,
which was 150% of the whole context window before it was fixed, and the
GGUF header parse, which has to skip a 150,000-entry string array to
reach the tensor table.
"""

import os
import struct
import tempfile
import unittest

from core import source_awareness
from editing import edit_guard


# Paths that must escape nothing, refused by both policies.
ESCAPES = (
    "../outside.txt",
    "../../etc/passwd",
    "..\\..\\windows\\system32\\config\\sam",
    "/etc/shadow",
    "C:\\Windows\\win.ini",
    "assistant/../../escape.py",
    "",
    "   ",
)


def _string(text):
    raw = text.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _kv_string(key, value):
    return _string(key) + struct.pack("<I", 8) + _string(value)


def _kv_u32(key, value):
    return _string(key) + struct.pack("<I", 4) + struct.pack("<I", value)


def _kv_string_array(key, values):
    body = _string(key) + struct.pack("<I", 9) + struct.pack("<I", 8)
    body += struct.pack("<Q", len(values))
    return body + b"".join(_string(value) for value in values)


def _tensor(name, dims, type_code, offset):
    body = _string(name) + struct.pack("<I", len(dims))
    body += b"".join(struct.pack("<Q", dim) for dim in dims)
    return body + struct.pack("<I", type_code) + struct.pack("<Q", offset)


def _write_gguf(path):
    """
    A minimal but structurally real GGUF v3 file.

    Built here rather than pointed at the bundled model so the suite still
    runs on a machine that has never downloaded one. The string array is
    the point of the fixture: the real tokeniser vocabulary is 150,000
    strings, and the parser has to seek past it rather than read it.
    """
    pairs = (
        _kv_string("general.architecture", "testarch")
        + _kv_string("general.name", "Test Model")
        + _kv_u32("testarch.block_count", 4)
        + _kv_u32("testarch.embedding_length", 256)
        + _kv_string_array("tokenizer.ggml.tokens", ["a", "bb", "ccc"])
    )
    tensors = (
        _tensor("blk.0.attn_q.weight", [256, 256], 8, 0)
        + _tensor("output_norm.weight", [256], 0, 65536)
    )
    header = (
        b"GGUF"
        + struct.pack("<I", 3)
        + struct.pack("<Q", 2)
        + struct.pack("<Q", 5)
    )

    with open(path, "wb") as handle:
        handle.write(header + pairs + tensors)


class ContainmentTests(unittest.TestCase):
    def test_both_policies_refuse_every_escape(self):
        for path in ESCAPES:
            with self.subTest(path=path):
                with self.assertRaises(edit_guard.GuardError):
                    edit_guard.resolve(path)
                with self.assertRaises(source_awareness.SourceError):
                    source_awareness.resolve_for_read(path)

    def test_reading_is_not_editing(self):
        # The design claim in one assertion: refused for writing, allowed
        # for reading. If this ever inverts, the manifest goes blind to
        # precisely the modules it most needs to describe.
        for relative in edit_guard.DENIED_FILES:
            protected = os.path.join("assistant", relative).replace("\\", "/")

            with self.subTest(path=protected):
                with self.assertRaises(edit_guard.GuardError):
                    edit_guard.resolve(relative)

                self.assertTrue(
                    os.path.isfile(source_awareness.resolve_for_read(protected))
                )

    def test_the_module_cannot_rewrite_itself(self):
        listed = {
            os.path.normpath(path).replace("\\", "/").casefold()
            for path in edit_guard.DENIED_FILES
        }
        self.assertIn("core/source_awareness.py", listed)


class ExclusionTests(unittest.TestCase):
    def test_credentials_are_refused(self):
        for path in (
            "assistant/.model_api_key",
            "assistant\\.model_api_key",
            "somewhere/.env",
            "certs/server.pem",
            "keys/private.key",
        ):
            with self.subTest(path=path):
                with self.assertRaises(source_awareness.SourceError):
                    source_awareness.resolve_for_read(path)

    def test_weight_files_are_refused_and_say_why(self):
        # Refused as a read path, not as knowledge: the header is reported
        # by gguf_identity(). The error has to point there, or the refusal
        # reads as secrecy about something the model is already told.
        #
        # These paths sit in the source tree rather than under models/,
        # which is not guaranteed to be a real directory. An operator short
        # of disk may relocate models/ to another drive with a junction --
        # the install wants about 55GB -- and realpath() then resolves it
        # outside the project, so containment refuses first and the message
        # differs. Asserting this wording on a models/ path made the suite
        # fail on a legitimate install; found by running it inside one.
        for path in (
            "assistant/core/pretend-model-q8_0.gguf",
            "assistant/pretend.safetensors",
            "assistant/tests/pretend.pt",
        ):
            with self.subTest(path=path):
                with self.assertRaises(source_awareness.SourceError) as caught:
                    source_awareness.resolve_for_read(path)

                self.assertIn("weights file", str(caught.exception))

    def test_a_relocated_weights_path_is_still_refused(self):
        # The other half of the note above. Which rule fires depends on
        # where the operator put the file; that it is refused does not.
        with self.assertRaises(source_awareness.SourceError):
            source_awareness.resolve_for_read("../elsewhere/model-q8_0.gguf")


class ReadingTests(unittest.TestCase):
    def test_truncation_is_announced_not_silent(self):
        # A silent truncation is the failure this module exists to stop:
        # it would let a confident summary be built from a fragment with
        # nothing in the context saying so.
        text = source_awareness.read_source(
            "assistant/core/config.py", max_bytes=1000
        )
        self.assertIn("[truncated:", text)
        self.assertIn("not the whole file", text)

    def test_missing_file_is_an_error_not_an_empty_string(self):
        with self.assertRaises(source_awareness.SourceError):
            source_awareness.read_source("assistant/core/no_such_module.py")


class WeightsIdentityTests(unittest.TestCase):
    def test_header_survives_a_string_array(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "fixture.gguf")
            _write_gguf(path)

            identity = source_awareness.gguf_identity(path)

        self.assertIsNotNone(identity)
        self.assertEqual(identity["gguf_version"], 3)
        self.assertEqual(identity["tensor_count"], 2)
        self.assertEqual(
            identity["fields"]["general.architecture"], "testarch"
        )
        self.assertEqual(identity["fields"]["testarch.block_count"], 4)
        self.assertEqual(identity["tensor_types"], {"Q8_0": 1, "F32": 1})

    def test_a_missing_or_corrupt_model_returns_none(self):
        # Degrading to silence is required. A model file that is absent or
        # half-written must cost the weights paragraph, never the turn.
        self.assertIsNone(source_awareness.gguf_identity("/nonexistent.gguf"))

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "garbage.gguf")

            with open(path, "wb") as handle:
                handle.write(b"NOTGGUF" + b"\x00" * 64)

            self.assertIsNone(source_awareness.gguf_identity(path))


class ManifestTests(unittest.TestCase):
    def test_manifest_states_the_rule_it_exists_to_enforce(self):
        manifest = source_awareness.manifest_text()

        self.assertTrue(manifest)
        self.assertIn("say so rather than", manifest)
        self.assertIn("not a memory of doing the work", manifest)

    def test_manifest_leaks_no_credential(self):
        self.assertNotIn(".model_api_key", source_awareness.manifest_text())

    def test_manifest_stays_affordable(self):
        # The first draft listed every file and came to 49,091 characters
        # -- about 12,000 tokens against an 8192 window, or 150% of the
        # context before a word of conversation. This is the bound that
        # stops that returning quietly.
        manifest = source_awareness.manifest_text()
        self.assertLess(
            len(manifest), 4000,
            f"manifest grew to {len(manifest)} chars "
            f"(~{len(manifest) // 4} tokens); it is resent every turn",
        )


if __name__ == "__main__":
    unittest.main()
