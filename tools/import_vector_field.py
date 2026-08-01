"""Import the shipped researchC vector field into an installed library.

The field is 15,000 embeddings the maintainer already paid the compute for.
Without it a new install either waits out that pass on its own hardware or
searches the shelf by keyword alone. With it, semantic retrieval works on
first run.

What makes that safe is the identity check. A vector only means something
beside the exact embedder and text policy that produced it, so this script
does not take the field's word for what it is: it recomputes the identity
from the installation it is running inside -- the model file on disk and the
truncation policy in library.py -- and refuses if the field disagrees. That
is also what couples this to the library.py in the same patch. Run the field
against an unpatched install and the policy string differs, so it stops
rather than seeding a cosine space with vectors built under another rule.

Rows are keyed by content_hash, which is a pure function of the chunk's text,
because chunk ids belong to whichever machine indexed the shelf. A chunk that
is not on this installation simply goes unfilled, and an existing vector is
never overwritten.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sqlite3
import struct
import sys
import zlib


MAGIC = "SABLEVEC1"
SIDECAR_FORMAT = "SABLERESEARCHC_VECTOR_FIELD1"
FIELD_NAME = "SABLERESEARCHC-VECTOR-FIELD.png"
KEYS_NAME = "VECTOR_FIELD_KEYS.json.gz"


class ImportError_(RuntimeError):
    """The field cannot be trusted against this installation."""


def read_sablevec(path: Path):
    """Decode a SABLEVEC1 set without depending on the research codec.

    The encoder writes 8-bit RGBA with filter type 0 on every scanline, so
    the recovery is a zlib inflate and a per-row filter byte to drop. Any
    other filter means the file is not the one that shipped, and that is
    worth stopping for rather than decoding into plausible nonsense.
    """
    blob = path.read_bytes()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ImportError_(f"{path.name} is not a PNG")

    header = None
    idat = b""
    width = height = None
    pos = 8
    while pos < len(blob):
        length, = struct.unpack(">I", blob[pos:pos + 4])
        kind = blob[pos + 4:pos + 8]
        chunk = blob[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, colour = struct.unpack(">IIBB", chunk[:10])
            if depth != 8 or colour != 6:
                raise ImportError_("expected 8-bit RGBA")
        elif kind == b"tEXt":
            key, _, value = chunk.partition(b"\0")
            if key == b"Comment":
                candidate = json.loads(value.decode("latin-1"))
                if candidate.get("magic") == MAGIC:
                    header = candidate
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
        pos += 12 + length

    if header is None:
        raise ImportError_(f"no {MAGIC} header in {path.name}")

    raw = zlib.decompress(idat)
    stride = width * 4
    dims = int(header["dims"])
    scale = float(header["scale"])
    low = float(header["low"])

    vectors = []
    at = 0
    for _ in range(height):
        if raw[at] != 0:
            raise ImportError_(
                f"scanline filter {raw[at]} is not the filter 0 this format "
                "writes; the field is not the file that shipped"
            )
        at += 1
        line = raw[at:at + stride]
        at += stride
        flat = bytearray()
        for x in range(width):
            flat += line[x * 4:x * 4 + 3]
        vectors.append([low + flat[i] * scale for i in range(dims)])
    return vectors, header


def installed_identity(install_root: Path) -> str:
    """Recompute the vector identity from this installation's own code."""
    assistant = install_root / "assistant"
    if not assistant.is_dir():
        raise ImportError_(f"no assistant/ under {install_root}")
    if str(assistant) not in sys.path:
        sys.path.insert(0, str(assistant))
    try:
        from core import embedding_server
        from knowledge import library
    except Exception as error:  # pragma: no cover - depends on the install
        raise ImportError_(f"could not import the installed library: {error}")
    return (
        f"{embedding_server.model_identity()}"
        f"+{library.EMBED_TRUNCATION_POLICY}"
    )


def apply_field(database: Path, hashes, vectors, identity) -> dict:
    connection = sqlite3.connect(str(database), timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT id, content_hash, vector, vector_model FROM chunks"
        ).fetchall()
        if not rows:
            raise ImportError_(
                "the library has no chunks yet -- run 'library rebuild' in "
                "the assistant first, then run this again"
            )

        wanted = {}
        for index, digest in enumerate(hashes):
            wanted.setdefault(digest, index)

        updates = []
        already = 0
        for row in rows:
            index = wanted.get(row["content_hash"])
            if index is None:
                continue
            if row["vector"] and row["vector_model"] == identity:
                already += 1
                continue
            payload = struct.pack(
                f"<{len(vectors[index])}f", *vectors[index]
            )
            updates.append((payload, identity, row["id"]))

        connection.executemany(
            "UPDATE chunks SET vector=?, vector_model=? WHERE id=?",
            updates,
        )
        if updates:
            # The assistant keeps the scored vectors in memory and reloads
            # them when this counter moves. This import runs in its own
            # process, so nothing else would tell a running instance that the
            # population underneath it had just changed.
            connection.execute(
                """
                INSERT INTO library_meta(key, value)
                VALUES('vector_generation', '1')
                ON CONFLICT(key) DO UPDATE
                SET value = CAST(
                    CAST(library_meta.value AS INTEGER) + 1 AS TEXT
                )
                """
            )
        connection.commit()
        return {
            "chunks_on_disk": len(rows),
            "field_rows": len(hashes),
            "filled": len(updates),
            "already_current": already,
        }
    finally:
        connection.close()


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        default=str(here.parents[2]),
        help="the installed release root (default: three levels up)",
    )
    parser.add_argument("--field", default=str(here / FIELD_NAME))
    parser.add_argument("--keys", default=str(here / KEYS_NAME))
    arguments = parser.parse_args()

    install_root = Path(arguments.target).resolve()
    database = install_root / "assistant" / "knowledge" / "library.sqlite3"

    try:
        if not database.is_file():
            raise ImportError_(f"no library database at {database}")

        with gzip.open(arguments.keys, "rt", encoding="utf-8") as handle:
            sidecar = json.load(handle)
        if sidecar.get("format") != SIDECAR_FORMAT:
            raise ImportError_("the keys sidecar is not a researchC field")

        identity = installed_identity(install_root)
        shipped = sidecar["vector_identity"]
        if shipped != identity:
            raise ImportError_(
                "this field was not built for this installation.\n"
                f"  field       : {shipped}\n"
                f"  installation: {identity}\n"
                "The embedder or the text policy differs, so the vectors "
                "would not share a cosine space with locally computed ones."
            )

        vectors, header = read_sablevec(Path(arguments.field))
        hashes = sidecar["content_hashes"]
        if len(vectors) != len(hashes):
            raise ImportError_(
                f"{len(vectors)} vectors but {len(hashes)} keys"
            )
        if int(header["dims"]) != int(sidecar["dims"]):
            raise ImportError_("field and sidecar disagree on dimensions")

        report = apply_field(database, hashes, vectors, identity)
    except ImportError_ as error:
        print(f"\n  Refused: {error}\n")
        return 1

    print(f"\n  Vector field imported into {database.name}.")
    print(f"    field rows        : {report['field_rows']}")
    print(f"    chunks on disk    : {report['chunks_on_disk']}")
    print(f"    vectors filled    : {report['filled']}")
    print(f"    already current   : {report['already_current']}")
    if not report["filled"] and not report["already_current"]:
        print(
            "\n  Nothing matched. That usually means the offline library "
            "patch\n  is not installed, or 'library rebuild' has not run "
            "yet.\n"
        )
        return 1
    print("\n  Semantic search is ready; no local embedding pass needed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
