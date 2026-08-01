"""Export the shipped researchC vector field as a SABLEVEC1 set.

The field is the canonical embed target -- the top EMBED_GLOBAL_CEILING chunks
by fair_rank -- exported in that same order, so the file's row order is the
shelf's own fairness order rather than an accident of chunk id.

A vector is only meaningful beside the identity that produced it, and a chunk
id is local to whichever machine indexed the shelf. So the set ships with two
things the raw coordinates cannot carry: the vector identity, and one
content_hash per row. The importer keys on the hash, which is a pure function
of the chunk's text, and refuses outright if the identity does not match the
installation it is being imported into.

Quantisation is SABLEVEC1's affine uint8, and the cosine cost of it is
measured here and written into the sidecar rather than assumed.
"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "tools", ROOT / "assistant"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import vector_pixel_codec as codec  # noqa: E402
from knowledge import library as L  # noqa: E402


FIELD_NAME = "SABLERESEARCHC-VECTOR-FIELD.png"
KEYS_NAME = "VECTOR_FIELD_KEYS.json.gz"


def load_target(database: Path, identity: str):
    """The exact embed target, in fair_rank order, with hashes and vectors."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            L._EMBED_TARGET_CTE + """
            SELECT id, content_hash, vector, vector_model
            FROM embed_target
            ORDER BY fair_rank
            """,
            L.KnowledgeLibrary._target_parameters(identity),
        ).fetchall()
    finally:
        connection.close()
    return rows


def export(database: Path, out_dir: Path) -> dict:
    identity = L._library._vector_identity()
    rows = load_target(database, identity)

    if not rows:
        raise SystemExit("the embed target is empty")

    missing = [
        row["id"] for row in rows
        if not row["vector"] or row["vector_model"] != identity
    ]
    if missing:
        raise SystemExit(
            f"{len(missing)} of {len(rows)} target rows are not embedded "
            f"under {identity}; first missing chunk id {missing[0]}. "
            "Finish the embed pass before exporting."
        )

    vectors = []
    hashes = []
    dims = None
    for row in rows:
        blob = row["vector"]
        if len(blob) % 4:
            raise SystemExit(f"chunk {row['id']} has a truncated vector blob")
        vector = list(struct.unpack(f"<{len(blob) // 4}f", blob))
        if dims is None:
            dims = len(vector)
        elif len(vector) != dims:
            raise SystemExit(
                f"chunk {row['id']} has {len(vector)} dims, expected {dims}"
            )
        if not row["content_hash"]:
            raise SystemExit(f"chunk {row['id']} has no content_hash")
        vectors.append(vector)
        hashes.append(row["content_hash"])

    if len(set(hashes)) != len(hashes):
        # Two chunks with identical text share a hash, and the importer would
        # fill both from whichever row it saw last. Identical text means an
        # identical vector, so this is safe -- but it must be visible.
        duplicates = len(hashes) - len(set(hashes))
        print(f"note: {duplicates} duplicate content_hash rows in the target")

    out_dir.mkdir(parents=True, exist_ok=True)
    field = out_dir / FIELD_NAME
    codec.encode(
        vectors,
        str(field),
        note=(
            f"researchC shipped vector field: {len(vectors)} chunk embeddings "
            f"in fair_rank order, identity {identity}"
        ),
    )

    recovered, header = codec.decode(str(field))
    cosines = sorted(
        codec.cosine(a, b) for a, b in zip(vectors, recovered)
    )
    loss = {
        "min": cosines[0],
        "p01": cosines[len(cosines) // 100],
        "p50": cosines[len(cosines) // 2],
        "mean": sum(cosines) / len(cosines),
    }

    sidecar = {
        "format": "SABLERESEARCHC_VECTOR_FIELD1",
        "vector_identity": identity,
        "dims": dims,
        "count": len(vectors),
        "order": "fair_rank",
        "quantisation_cosine": loss,
        "content_hashes": hashes,
    }
    keys = out_dir / KEYS_NAME
    with gzip.open(keys, "wt", encoding="utf-8", newline="\n") as handle:
        json.dump(sidecar, handle, sort_keys=True)

    return {
        "identity": identity,
        "count": len(vectors),
        "dims": dims,
        "field_bytes": field.stat().st_size,
        "keys_bytes": keys.stat().st_size,
        "quantisation_cosine": loss,
        "field": str(field),
        "keys": str(keys),
    }


def main() -> None:
    database = Path(
        sys.argv[1] if len(sys.argv) > 1
        else ROOT / "assistant" / "knowledge" / "library.sqlite3"
    )
    out_dir = Path(
        sys.argv[2] if len(sys.argv) > 2
        else ROOT.parent / "SABLERESEARCHC" / "stage-vector-field"
    )
    report = export(database, out_dir)
    print(f"identity   {report['identity']}")
    print(f"vectors    {report['count']} x {report['dims']}")
    print(f"field      {report['field_bytes']} bytes  {report['field']}")
    print(f"keys       {report['keys_bytes']} bytes  {report['keys']}")
    loss = report["quantisation_cosine"]
    print(
        "cosine     min %.6f  p01 %.6f  p50 %.6f  mean %.6f"
        % (loss["min"], loss["p01"], loss["p50"], loss["mean"])
    )


if __name__ == "__main__":
    main()
