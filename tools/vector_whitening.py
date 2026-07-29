"""Versioned, regularised whitening for embedding-space experiments.

Whitening changes a representation's geometry.  It is therefore deliberately
not a hidden pre-processing step for memory retrieval or machinespirit.  Fit
one transform on a declared reference corpus, bind it to that corpus and its
model metadata, then apply the same transform to every vector being compared.

The default uses shrinkage because the project's reference sets are often
smaller than an embedding's dimensionality.  Unregularised whitening in that
case would invert zero-variance directions and amplify numerical noise.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np


MAGIC = "SABLEWHITE1"
VERSION = 1
METHOD = "zca-shrinkage"


class WhiteningError(ValueError):
    """A transform or vector is not safe to use for a geometric comparison."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def _vectors(vectors: Sequence[Sequence[float]], minimum_rows: int = 1):
    try:
        rows = np.asarray(vectors, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise WhiteningError("vectors must be a rectangular numeric matrix") from error

    if rows.ndim != 2 or rows.shape[0] < minimum_rows or rows.shape[1] == 0:
        raise WhiteningError(
            f"need at least {minimum_rows} non-empty vectors")
    if not np.all(np.isfinite(rows)):
        raise WhiteningError("vectors contain a non-finite value")
    return rows


def vector_digest(vectors: Sequence[Sequence[float]]) -> str:
    """Digest an exact float64 matrix shape and payload, not its JSON spelling."""
    rows = _vectors(vectors)
    payload = np.ascontiguousarray(rows.astype("<f8", copy=False))
    digest = hashlib.sha256()
    digest.update(np.asarray(payload.shape, dtype="<i8").tobytes())
    digest.update(payload.tobytes())
    return digest.hexdigest()


def unit(vector: Sequence[float]) -> list[float]:
    """L2-normalise one transformed vector, refusing a collapsed result."""
    row = _vectors([vector])[0]
    length = float(np.linalg.norm(row))
    if not math.isfinite(length) or length <= 0.0:
        raise WhiteningError("whitening produced a zero-length vector")
    return (row / length).tolist()


@dataclass
class WhiteningTransform:
    """A fitted ZCA transform plus enough provenance to refuse mismatches."""

    mean: np.ndarray
    matrix: np.ndarray
    samples: int
    shrinkage: float
    eigenvalue_floor: float
    training_digest: str
    metadata: dict[str, Any]

    @property
    def dimensions(self) -> int:
        return int(self.mean.shape[0])

    def transform(self, vector: Sequence[float], normalise: bool = False):
        row = _vectors([vector])[0]
        if row.shape[0] != self.dimensions:
            raise WhiteningError(
                f"vector has {row.shape[0]} dimensions, expected {self.dimensions}")
        result = (row - self.mean) @ self.matrix
        if not np.all(np.isfinite(result)):
            raise WhiteningError("whitening produced a non-finite vector")
        return unit(result) if normalise else result.tolist()

    def transform_many(
        self, vectors: Sequence[Sequence[float]], normalise: bool = False,
    ):
        rows = _vectors(vectors)
        if rows.shape[1] != self.dimensions:
            raise WhiteningError(
                f"vectors have {rows.shape[1]} dimensions, expected {self.dimensions}")
        result = (rows - self.mean) @ self.matrix
        if not np.all(np.isfinite(result)):
            raise WhiteningError("whitening produced a non-finite vector")
        if normalise:
            lengths = np.linalg.norm(result, axis=1)
            if np.any(~np.isfinite(lengths)) or np.any(lengths <= 0.0):
                raise WhiteningError("whitening produced a zero-length vector")
            result = result / lengths[:, None]
        return result.tolist()

    def assert_compatible(self, metadata: Mapping[str, Any]) -> None:
        """Refuse use under a different declared model/reference identity."""
        try:
            supplied = _canonical(dict(metadata))
        except (TypeError, ValueError) as error:
            raise WhiteningError(
                "compatibility metadata must be JSON serialisable"
            ) from error
        if supplied != _canonical(self.metadata):
            raise WhiteningError(
                "whitening transform metadata does not match this comparison"
            )

    def document(self, include_digest: bool = True) -> dict[str, Any]:
        document = {
            "magic": MAGIC,
            "version": VERSION,
            "method": METHOD,
            "dimensions": self.dimensions,
            "samples": self.samples,
            "shrinkage": self.shrinkage,
            "eigenvalue_floor": self.eigenvalue_floor,
            "training_digest": self.training_digest,
            "metadata": self.metadata,
            "mean": self.mean.tolist(),
            "matrix": self.matrix.tolist(),
        }
        if include_digest:
            document["digest"] = hashlib.sha256(
                _canonical(document)
            ).hexdigest()
        return document


def fit(
    vectors: Sequence[Sequence[float]], *, shrinkage: float = 0.10,
    eigenvalue_floor: float = 1e-6, metadata: Mapping[str, Any] | None = None,
) -> WhiteningTransform:
    """Fit a regularised ZCA whitening transform.

    ``shrinkage`` mixes every covariance eigenvalue toward the mean variance.
    It makes a transform well-defined when samples are fewer than dimensions.
    ``eigenvalue_floor`` is relative to that mean variance and prevents a
    nearly-null direction from becoming an enormous multiplier.
    """
    if not 0.0 <= shrinkage <= 1.0:
        raise WhiteningError("shrinkage must lie between zero and one")
    if not math.isfinite(eigenvalue_floor) or eigenvalue_floor <= 0.0:
        raise WhiteningError("eigenvalue_floor must be positive and finite")

    rows = _vectors(vectors, minimum_rows=2)
    mean = rows.mean(axis=0)
    centred = rows - mean
    covariance = (centred.T @ centred) / (rows.shape[0] - 1)
    covariance = (covariance + covariance.T) * 0.5
    average_variance = float(np.trace(covariance) / rows.shape[1])
    if not math.isfinite(average_variance) or average_variance <= 0.0:
        raise WhiteningError("reference vectors have no usable variance")

    values, basis = np.linalg.eigh(covariance)
    regularised = ((1.0 - shrinkage) * values
                   + shrinkage * average_variance)
    floor = average_variance * eigenvalue_floor
    regularised = np.maximum(regularised, floor)
    scales = 1.0 / np.sqrt(regularised)
    matrix = (basis * scales) @ basis.T
    matrix = (matrix + matrix.T) * 0.5

    clean_metadata = dict(metadata or {})
    try:
        _canonical(clean_metadata)
    except (TypeError, ValueError) as error:
        raise WhiteningError("metadata must be JSON serialisable") from error

    return WhiteningTransform(
        mean=mean,
        matrix=matrix,
        samples=int(rows.shape[0]),
        shrinkage=float(shrinkage),
        eigenvalue_floor=float(eigenvalue_floor),
        training_digest=vector_digest(rows.tolist()),
        metadata=clean_metadata,
    )


def from_document(document: Mapping[str, Any]) -> WhiteningTransform:
    """Load a transform only when its shape, finiteness, and digest agree."""
    if not isinstance(document, Mapping):
        raise WhiteningError("whitening document must be an object")
    required = {"magic", "version", "method", "dimensions", "samples",
                "shrinkage", "eigenvalue_floor", "training_digest",
                "metadata", "mean", "matrix", "digest"}
    if set(document) != required:
        raise WhiteningError("whitening document has missing or unknown fields")
    if document["magic"] != MAGIC or document["version"] != VERSION:
        raise WhiteningError("not a supported SABLE whitening transform")
    if document["method"] != METHOD:
        raise WhiteningError("unsupported whitening method")

    unsigned = dict(document)
    recorded = unsigned.pop("digest")
    if not isinstance(recorded, str) or hashlib.sha256(_canonical(unsigned)).hexdigest() != recorded:
        raise WhiteningError("whitening document digest does not verify")

    dimensions = document["dimensions"]
    samples = document["samples"]
    if (not isinstance(dimensions, int) or dimensions <= 0
            or not isinstance(samples, int) or samples < 2):
        raise WhiteningError("whitening document has invalid dimensions or samples")
    try:
        mean = np.asarray(document["mean"], dtype=np.float64)
        matrix = np.asarray(document["matrix"], dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise WhiteningError("whitening document has non-numeric coordinates") from error
    if mean.shape != (dimensions,) or matrix.shape != (dimensions, dimensions):
        raise WhiteningError("whitening document matrix shape does not match dimensions")
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(matrix)):
        raise WhiteningError("whitening document contains a non-finite value")
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1e-10):
        raise WhiteningError("whitening matrix must be symmetric")

    shrinkage = document["shrinkage"]
    floor = document["eigenvalue_floor"]
    if (not isinstance(shrinkage, (int, float)) or isinstance(shrinkage, bool)
            or not 0.0 <= shrinkage <= 1.0
            or not isinstance(floor, (int, float)) or isinstance(floor, bool)
            or not math.isfinite(floor) or floor <= 0.0):
        raise WhiteningError("whitening document has invalid regularisation")
    if not isinstance(document["training_digest"], str):
        raise WhiteningError("whitening document has no training digest")
    if not isinstance(document["metadata"], dict):
        raise WhiteningError("whitening document metadata must be an object")

    return WhiteningTransform(
        mean=mean,
        matrix=matrix,
        samples=samples,
        shrinkage=float(shrinkage),
        eigenvalue_floor=float(floor),
        training_digest=document["training_digest"],
        metadata=dict(document["metadata"]),
    )


def load(path: str | Path) -> WhiteningTransform:
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise WhiteningError(f"could not read whitening document: {error}") from error
    return from_document(document)


def save(transform: WhiteningTransform, path: str | Path):
    """Write the canonical, self-verifying transform document."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(transform.document(), handle, sort_keys=True,
                  separators=(",", ":"), ensure_ascii=True)
        handle.write("\n")


def _read_vectors(path: str | Path):
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    if isinstance(document, list):
        return document
    if isinstance(document, dict) and isinstance(document.get("vectors"), list):
        return document["vectors"]
    raise WhiteningError("input must be a vector list or an object with vectors")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    fitting = commands.add_parser("fit", help="fit a transform from JSON vectors")
    fitting.add_argument("--input", required=True)
    fitting.add_argument("--output", required=True)
    fitting.add_argument("--shrinkage", type=float, default=0.10)
    fitting.add_argument("--eigenvalue-floor", type=float, default=1e-6)
    fitting.add_argument("--model", help="model identity to bind into metadata")
    fitting.add_argument("--pooling", help="pooling mode to bind into metadata")
    applying = commands.add_parser("apply", help="apply a transform to JSON vectors")
    applying.add_argument("--transform", required=True)
    applying.add_argument("--input", required=True)
    applying.add_argument("--output", required=True)
    applying.add_argument("--normalise", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "fit":
        metadata = {key: value for key, value in {
            "model": args.model, "pooling": args.pooling,
        }.items() if value}
        transform = fit(
            _read_vectors(args.input), shrinkage=args.shrinkage,
            eigenvalue_floor=args.eigenvalue_floor, metadata=metadata,
        )
        save(transform, args.output)
        print(f"wrote {args.output}")
        print(f"  {transform.dimensions} dimensions, {transform.samples} samples")
        print(f"  digest {transform.document()['digest']}")
        return 0

    transform = load(args.transform)
    rows = transform.transform_many(_read_vectors(args.input), args.normalise)
    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"vectors": rows, "transform_digest": transform.document()["digest"]},
                  handle, separators=(",", ":"), ensure_ascii=True)
        handle.write("\n")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
