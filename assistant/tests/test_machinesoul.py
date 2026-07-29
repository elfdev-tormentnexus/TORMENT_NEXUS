"""Tests for the MACHINESOUL1 capsule.

A container that carries a release has exactly one job beyond carrying it:
never hand back bytes that are not the payload. Every test here is about a
way that could happen quietly -- a flipped pixel, a truncated file, a PNG
that is not a capsule at all, an archive entry pointing outside the target.
None of those raise on their own, so each gets a guard and each guard is
checked against the defect it exists for.
"""
import hashlib
import importlib.util
import io
import os
import shutil
import struct
import tarfile
import tempfile
import unittest
import zlib

# Loaded by path, the way test_vector_beam.py loads its tool: a plain
# `import machinesoul` reads as an undeclared third-party package to the
# dependency scanner in test_regressions.py, which cannot tell a tools/
# module from something that needs to be pip installed.
_CAPSULE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tools",
    "machinesoul.py",
)
_spec = importlib.util.spec_from_file_location("_machinesoul_under_test",
                                               _CAPSULE)
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def write_raw(blob, path, width=sc.WIDTH, frames=4):
    """Emit a capsule-shaped PNG around arbitrary pixel bytes.

    Used to build files that are structurally valid and semantically wrong,
    which is the only way to test that the checksum is load-bearing.
    """
    stride = width * sc.CHANNELS
    height = max(1, -(-len(blob) // (stride * frames)))
    blob = blob + b"\x00" * (stride * height * frames - len(blob))
    out = [b"\x89PNG\r\n\x1a\n",
           sc._chunk(b"IHDR",
                     struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
           sc._chunk(b"acTL", struct.pack(">II", frames, 0))]
    span = stride * height
    sequence = 0
    for index in range(frames):
        raw = b"".join(sc._rows(blob[index * span:(index + 1) * span], width))
        out.append(sc._chunk(b"fcTL", struct.pack(
            ">IIIIIHHBB", sequence, width, height, 0, 0, 120, 1000, 0, 0)))
        sequence += 1
        if index == 0:
            out.append(sc._chunk(b"IDAT", zlib.compress(raw, 9)))
        else:
            out.append(sc._chunk(
                b"fdAT", struct.pack(">I", sequence) + zlib.compress(raw, 9)))
            sequence += 1
    out.append(sc._chunk(b"IEND", b""))
    with open(path, "wb") as handle:
        handle.write(b"".join(out))


def header_for(payload, frames=4):
    return (sc.MAGIC + bytes([sc.VERSION]) + struct.pack(">Q", len(payload))
            + struct.pack(">I", frames) + hashlib.sha256(payload).digest())


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder,
                        ignore_errors=True)
        self.capsule = os.path.join(self.folder, "c.png")

    def test_payload_survives_byte_for_byte(self):
        payload = bytes(range(256)) * 40
        sc.build(payload, self.capsule, frames=4)
        recovered, meta = sc.extract(self.capsule)
        self.assertEqual(recovered, payload)
        self.assertEqual(meta["length"], len(payload))

    def test_an_empty_payload_round_trips(self):
        sc.build(b"", self.capsule, frames=1)
        recovered, _ = sc.extract(self.capsule)
        self.assertEqual(recovered, b"")

    def test_a_payload_that_does_not_fill_the_last_frame_round_trips(self):
        """Filler must not be mistaken for payload."""
        payload = b"x" * 1001
        sc.build(payload, self.capsule, frames=8)
        recovered, _ = sc.extract(self.capsule)
        self.assertEqual(recovered, payload)

    def test_the_file_is_a_real_apng_with_the_declared_frame_count(self):
        sc.build(b"y" * 5000, self.capsule, frames=5)
        with open(self.capsule, "rb") as handle:
            blob = handle.read()
        self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n")
        index = blob.index(b"acTL")
        self.assertEqual(struct.unpack(">I", blob[index + 4:index + 8])[0], 5)
        self.assertEqual(blob.count(b"fcTL"), 5)

    def test_frames_carry_the_payload_rather_than_repeating_one(self):
        payload = os.urandom(8000)
        sc.build(payload, self.capsule, frames=4)
        self.assertEqual(sc.extract(self.capsule)[0], payload)


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder,
                        ignore_errors=True)
        self.capsule = os.path.join(self.folder, "c.png")

    def test_a_flipped_payload_byte_is_refused(self):
        """The guard the checksum exists for."""
        real = b"the release archive" * 200
        decoy = b"the release archive" * 200
        decoy = decoy[:-1] + bytes([decoy[-1] ^ 0x01])
        self.assertEqual(len(real), len(decoy))
        write_raw(header_for(real) + decoy, self.capsule)
        with self.assertRaises(sc.CapsuleError) as caught:
            sc.extract(self.capsule)
        self.assertIn("sha256 mismatch", str(caught.exception))

    def test_a_truncated_capsule_is_refused_rather_than_partly_returned(self):
        payload = b"z" * 9000
        blob = header_for(payload) + payload[:4000]
        write_raw(blob, self.capsule, frames=1)
        with self.assertRaises(sc.CapsuleError) as caught:
            sc.extract(self.capsule)
        self.assertIn("truncated", str(caught.exception))

    def test_an_ordinary_png_is_refused_with_the_re_encoding_explanation(self):
        write_raw(b"\x10\x20\x30\x40" * 500, self.capsule)
        with self.assertRaises(sc.CapsuleError) as caught:
            sc.extract(self.capsule)
        self.assertIn("re-encoded", str(caught.exception))

    def test_a_damaged_compressed_stream_is_refused_as_a_capsule_error(self):
        """Found by cutting researchA: zlib's own exception was escaping.

        Corruption inside the DEFLATE stream fails before any checksum runs,
        so without this the recipient of a damaged download gets a traceback
        instead of a sentence.
        """
        sc.build(b"payload" * 500, self.capsule, frames=2)
        with open(self.capsule, "rb") as handle:
            blob = bytearray(handle.read())
        start = blob.find(b"IDAT") + 40
        blob[start] ^= 0x01
        with open(self.capsule, "wb") as handle:
            handle.write(bytes(blob))
        with self.assertRaises(sc.CapsuleError) as caught:
            sc.extract(self.capsule)
        self.assertIn("damaged", str(caught.exception))

    def test_a_file_that_is_not_a_png_is_refused(self):
        with open(self.capsule, "wb") as handle:
            handle.write(b"PK\x03\x04 this is a zip")
        with self.assertRaises(sc.CapsuleError):
            sc.extract(self.capsule)

    def test_a_future_version_is_refused_rather_than_guessed(self):
        payload = b"later"
        header = (sc.MAGIC + bytes([sc.VERSION + 1])
                  + struct.pack(">Q", len(payload)) + struct.pack(">I", 1)
                  + hashlib.sha256(payload).digest())
        write_raw(header + payload, self.capsule, frames=1)
        with self.assertRaises(sc.CapsuleError) as caught:
            sc.extract(self.capsule)
        self.assertIn("version", str(caught.exception))

    def test_a_non_rgba_png_is_refused(self):
        body = struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0)   # colour type 2
        blob = (b"\x89PNG\r\n\x1a\n" + sc._chunk(b"IHDR", body)
                + sc._chunk(b"IDAT", zlib.compress(b"\x00" * 64))
                + sc._chunk(b"IEND", b""))
        with open(self.capsule, "wb") as handle:
            handle.write(blob)
        with self.assertRaises(sc.CapsuleError) as caught:
            sc.extract(self.capsule)
        self.assertIn("RGBA", str(caught.exception))


class StreamingTests(unittest.TestCase):
    """Bounded memory is the whole claim, so it is asserted rather than said."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.source = os.path.join(self.folder, "payload.bin")
        with open(self.source, "wb") as handle:
            handle.write((bytes(range(256)) * 40)[:9000])
        self.capsule = os.path.join(self.folder, "c.png")

    def test_a_streamed_capsule_reads_with_the_ordinary_extractor(self):
        """Same container from either builder, or the format has forked."""
        sc.build_stream(self.source, self.capsule, frame_rows=4)
        payload, meta = sc.extract(self.capsule)
        with open(self.source, "rb") as handle:
            self.assertEqual(payload, handle.read())
        self.assertEqual(meta["length"], os.path.getsize(self.source))

    def test_streaming_extract_recovers_an_in_memory_capsule(self):
        blob = b"either builder, either reader" * 40
        sc.build(blob, self.capsule, frames=3)
        out = os.path.join(self.folder, "out.bin")
        sc.extract_stream(self.capsule, out)
        with open(out, "rb") as handle:
            self.assertEqual(handle.read(), blob)

    def test_streaming_holds_far_less_than_the_payload(self):
        import tracemalloc

        big = os.path.join(self.folder, "big.bin")
        with open(big, "wb") as handle:
            handle.write(os.urandom(4 * 1024 * 1024))
        target = os.path.join(self.folder, "big.png")
        sc.build_stream(big, target, frame_rows=256)

        out = os.path.join(self.folder, "big_out.bin")
        tracemalloc.start()
        sc.extract_stream(target, out)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(peak, 2 * 1024 * 1024,
                        "extraction allocated on the order of the payload")
        self.assertEqual(os.path.getsize(out), os.path.getsize(big))

    def test_a_damaged_stream_is_refused_and_leaves_no_file(self):
        sc.build_stream(self.source, self.capsule, frame_rows=4)
        with open(self.capsule, "rb") as handle:
            blob = bytearray(handle.read())
        blob[blob.find(b"IDAT") + 30] ^= 0x01
        with open(self.capsule, "wb") as handle:
            handle.write(bytes(blob))
        out = os.path.join(self.folder, "must_not_exist.bin")
        with self.assertRaises(sc.CapsuleError):
            sc.extract_stream(self.capsule, out)
        self.assertFalse(os.path.exists(out),
                         "a refused extraction left a partial file behind")

    def test_a_truncated_stream_is_refused(self):
        sc.build_stream(self.source, self.capsule, frame_rows=4)
        with open(self.capsule, "rb") as handle:
            blob = handle.read()
        with open(self.capsule, "wb") as handle:
            handle.write(blob[:len(blob) // 2])
        out = os.path.join(self.folder, "partial.bin")
        with self.assertRaises(sc.CapsuleError):
            sc.extract_stream(self.capsule, out)
        self.assertFalse(os.path.exists(out))


class RefusalLeavesTheDiskAloneTests(unittest.TestCase):
    """"Nothing is kept" has to be true of the disk, not just the payload.

    A refused capsule said nothing was written while having already
    truncated whatever sat at --out, and an interrupted build left a
    partial capsule and a frame spill behind. Both are refusals that cost
    the operator a file.
    """

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.source = os.path.join(self.folder, "payload.bin")
        with open(self.source, "wb") as handle:
            handle.write((bytes(range(256)) * 40)[:9000])
        self.capsule = os.path.join(self.folder, "c.png")

    def test_a_refused_capsule_does_not_destroy_an_existing_file(self):
        sc.build_stream(self.source, self.capsule, frame_rows=4)

        with open(self.capsule, "r+b") as handle:      # break the payload
            handle.seek(-64, os.SEEK_END)
            handle.write(b"\x00" * 8)

        target = os.path.join(self.folder, "precious.tar")
        with open(target, "wb") as handle:
            handle.write(b"work that predates this extraction")

        with self.assertRaises(sc.CapsuleError):
            sc.extract_stream(self.capsule, target)

        with open(target, "rb") as handle:
            self.assertEqual(handle.read(),
                             b"work that predates this extraction")

    def test_a_refused_capsule_leaves_no_partial_beside_the_target(self):
        sc.build_stream(self.source, self.capsule, frame_rows=4)
        with open(self.capsule, "r+b") as handle:
            handle.seek(-64, os.SEEK_END)
            handle.write(b"\x00" * 8)

        target = os.path.join(self.folder, "out.tar")
        with self.assertRaises(sc.CapsuleError):
            sc.extract_stream(self.capsule, target)

        leftovers = [n for n in os.listdir(self.folder)
                     if n.startswith("out.tar")]
        self.assertEqual(leftovers, [])

    def test_an_interrupted_build_leaves_no_capsule_and_no_spill(self):
        def die(index, total):
            if index >= 2:
                raise KeyboardInterrupt("operator stopped the build")

        with self.assertRaises(KeyboardInterrupt):
            sc.build_stream(self.source, self.capsule, frame_rows=2,
                            progress=die)

        self.assertFalse(os.path.exists(self.capsule))
        self.assertFalse(os.path.exists(self.capsule + ".frame.tmp"))

    def test_a_successful_build_still_cleans_up_its_spill(self):
        sc.build_stream(self.source, self.capsule, frame_rows=4)
        self.assertTrue(os.path.exists(self.capsule))
        self.assertFalse(os.path.exists(self.capsule + ".frame.tmp"))


class DescriptionTests(unittest.TestCase):
    """A capsule may say what it carries. Two properties keep that honest.

    It sits outside the sha256 gate, so it is a hint and never a guarantee
    -- an unverified claim riding a verified one is the silent failure this
    project ranks worst. And it is readable by anyone holding the file, so
    it must never appear unless asked for.
    """

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        self.source = os.path.join(self.folder, "payload.bin")
        self.blob = b"ordered anchor decree " * 300
        with open(self.source, "wb") as handle:
            handle.write(self.blob)
        self.capsule = os.path.join(self.folder, "c.png")

    def test_a_capsule_carries_no_description_unless_asked(self):
        """Off by default, because describing private contents leaks them."""
        sc.build_stream(self.source, self.capsule)
        self.assertIsNone(sc.read_description(self.capsule))

    def test_a_description_reads_back_without_decoding_the_payload(self):
        text = "184 ordered anchors, core digest b5421687348e956e."
        sc.build_stream(self.source, self.capsule, description=text)
        self.assertEqual(sc.read_description(self.capsule), text)

    def test_the_in_memory_builder_carries_one_too(self):
        sc.build(self.blob, self.capsule, frames=2, description="a decree")
        self.assertEqual(sc.read_description(self.capsule), "a decree")

    def test_the_description_does_not_change_the_payload_or_its_digest(self):
        plain = os.path.join(self.folder, "plain.png")
        sc.build_stream(self.source, plain)
        sc.build_stream(self.source, self.capsule, description="anything")

        first = os.path.join(self.folder, "a.bin")
        second = os.path.join(self.folder, "b.bin")
        self.assertEqual(sc.extract_stream(plain, first)["sha256"],
                         sc.extract_stream(self.capsule, second)["sha256"])
        with open(first, "rb") as a, open(second, "rb") as b:
            self.assertEqual(a.read(), self.blob)
            self.assertEqual(b.read(), self.blob)

    def test_an_edited_description_does_not_fail_extraction(self):
        """It is outside the gate, and the test says so rather than the docs.

        This is the property that makes it a hint. If editing it broke
        extraction, it would be part of the guarantee, and it is not.
        """
        sc.build_stream(self.source, self.capsule, description="honest text")
        with open(self.capsule, "rb") as handle:
            blob = handle.read()
        tampered = blob.replace(b"honest text", b"dishonest!!")
        self.assertNotEqual(tampered, blob)
        with open(self.capsule, "wb") as handle:
            handle.write(tampered)

        out = os.path.join(self.folder, "still.bin")
        sc.extract_stream(self.capsule, out)          # must not raise
        with open(out, "rb") as handle:
            self.assertEqual(handle.read(), self.blob)

    def test_the_stored_text_warns_that_it_is_not_covered_by_the_digest(self):
        sc.build_stream(self.source, self.capsule, description="x")
        with open(self.capsule, "rb") as handle:
            raw = handle.read()
        self.assertIn(b"NOT covered", raw)

    def test_a_capsule_from_before_this_feature_still_reads(self):
        sc.build_stream(self.source, self.capsule)
        self.assertIsNone(sc.read_description(self.capsule))
        out = os.path.join(self.folder, "old.bin")
        sc.extract_stream(self.capsule, out)
        with open(out, "rb") as handle:
            self.assertEqual(handle.read(), self.blob)


class ArchiveSafetyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder,
                        ignore_errors=True)

    def _tar_with(self, name):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            info = tarfile.TarInfo(name)
            info.size = 3
            archive.addfile(info, io.BytesIO(b"bad"))
        return buffer.getvalue()

    def test_an_entry_escaping_the_target_is_refused(self):
        target = os.path.join(self.folder, "out")
        os.makedirs(target)
        blob = self._tar_with("../escaped.txt")
        with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
            with self.assertRaises(sc.CapsuleError) as caught:
                sc._safe_extract(archive, target)
        self.assertIn("escapes", str(caught.exception))
        self.assertFalse(os.path.exists(
            os.path.join(self.folder, "escaped.txt")))

    def test_an_absolute_entry_is_refused(self):
        target = os.path.join(self.folder, "out2")
        os.makedirs(target)
        blob = self._tar_with("/tmp/escaped.txt")
        with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
            try:
                sc._safe_extract(archive, target)
            except sc.CapsuleError:
                return
        # tarfile may already strip the leading slash; then it must land
        # inside the target rather than at the filesystem root.
        self.assertTrue(os.path.exists(os.path.join(target, "tmp",
                                                    "escaped.txt")))

    def test_the_tar_is_deterministic(self):
        source = os.path.join(self.folder, "src")
        os.makedirs(source)
        for name in ("b.txt", "a.txt"):
            with open(os.path.join(source, name), "w") as handle:
                handle.write(name)
        self.assertEqual(sc.tar_directory(source), sc.tar_directory(source))


if __name__ == "__main__":
    unittest.main()

