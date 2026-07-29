"""Measure regularised whitening without silently changing SABLE retrieval.

This is an experiment harness, not a runtime feature.  It fits a transform on
declared public reference documents, then compares raw and whitened anchor
reconstruction on a separate public test document.  Self-retrieval tells us
whether anchor coordinates preserve their source vector; it does *not* prove
that ordinary semantic retrieval improved.  That needs a labelled corpus.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "assistant"))

from core import embedding_server, machinespirit  # noqa: E402
import vector_whitening as white  # noqa: E402


MAX_CHARS = 800


def _chunks(path: str, limit: int | None):
    """Public paragraph chunks in the same bounded shape as Rosetta tests."""
    text = Path(path).read_text(encoding="utf-8")
    chunks = [part.strip().replace("\n", " ") for part in text.split("\n\n")]
    chunks = [part[:MAX_CHARS] for part in chunks if len(part) > 120]
    return chunks[:limit] if limit else chunks


def _document_digest(paths, chunks):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(Path(path).as_posix()).encode("utf-8"))
        digest.update(b"\x00")
    for chunk in chunks:
        digest.update(chunk.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def cosine(left, right):
    left_length = math.sqrt(sum(x * x for x in left)) or 1.0
    right_length = math.sqrt(sum(x * x for x in right)) or 1.0
    return sum(x * y for x, y in zip(left, right)) / (left_length * right_length)


def pairwise(values):
    rows = [cosine(values[i], values[j])
            for i in range(len(values)) for j in range(i + 1, len(values))]
    if not rows:
        return {"count": 0, "mean": None, "standard_deviation": None}
    mean = sum(rows) / len(rows)
    variance = sum((row - mean) ** 2 for row in rows) / len(rows)
    return {
        "count": len(rows),
        "mean": mean,
        "standard_deviation": math.sqrt(variance),
    }


def _codec_metrics(corpus, anchors):
    """Held-out anchor-coordinate reconstruction, measured symmetrically."""
    from machinespirit_codec import (
        decode_least_squares, encode, gram_matrix, retrieval_rank,
    )

    gram = gram_matrix(anchors)
    cosines = []
    ranks = []
    for index, vector in enumerate(corpus):
        rebuilt = decode_least_squares(encode(vector, anchors), anchors, gram=gram)
        cosines.append(cosine(vector, rebuilt))
        ranks.append(retrieval_rank(rebuilt, corpus, index))
    ranks_sorted = sorted(ranks)
    return {
        "mean_cosine": sum(cosines) / len(cosines),
        "worst_cosine": min(cosines),
        "recovered_at_1": sum(rank == 1 for rank in ranks) / len(ranks),
        "median_rank": ranks_sorted[len(ranks_sorted) // 2],
    }


def run(
    fit_paths, test_path, fit_limit=None, test_limit=None, shrinkage=0.10,
    eigenvalue_floor=1e-6,
):
    """Run one provenance-bound, held-out whitening comparison."""
    fit_chunks = []
    for path in fit_paths:
        fit_chunks.extend(_chunks(path, fit_limit))
    test_chunks = _chunks(test_path, test_limit)
    if len(fit_chunks) < 2 or len(test_chunks) < 2:
        raise ValueError("fit and test corpora each need at least two chunks")
    # A research probe may be pointed at a manually launched compatible
    # server.  Keep the application's alias check strict, but do not reject
    # that server here before the actual authenticated embedding requests
    # below have had a chance to establish whether it is usable.
    if not embedding_server._health_responds(timeout=5):
        raise RuntimeError("the local pooled embedding server is not answering")

    training_vectors = embedding_server.embed(fit_chunks, timeout=120)
    test_vectors = embedding_server.embed(test_chunks, timeout=120)
    anchor_texts = machinespirit.anchor_texts(True, True)
    anchor_vectors = embedding_server.embed(anchor_texts, timeout=120)
    if not training_vectors or not test_vectors or not anchor_vectors:
        raise RuntimeError("the local embedding server returned no vectors")

    metadata = {
        "model": embedding_server.model_identity(),
        "pooling": embedding_server.POOLING_MODE,
        "reference_documents": [str(Path(path).as_posix()) for path in fit_paths],
        "reference_document_digest": _document_digest(fit_paths, fit_chunks),
    }
    transform = white.fit(
        training_vectors, shrinkage=shrinkage,
        eigenvalue_floor=eigenvalue_floor, metadata=metadata,
    )
    white_test = transform.transform_many(test_vectors, normalise=True)
    white_anchors = transform.transform_many(anchor_vectors, normalise=True)
    raw_test = [white.unit(row) for row in test_vectors]
    raw_anchors = [white.unit(row) for row in anchor_vectors]

    return {
        "experiment": "SABLEWHITE1 held-out anchor codec comparison",
        "fit": {
            "documents": [str(Path(path).as_posix()) for path in fit_paths],
            "chunks": len(fit_chunks),
            "document_digest": metadata["reference_document_digest"],
        },
        "test": {"document": str(Path(test_path).as_posix()), "chunks": len(test_chunks)},
        "transform": {
            "digest": transform.document()["digest"],
            "dimensions": transform.dimensions,
            "samples": transform.samples,
            "shrinkage": transform.shrinkage,
            "eigenvalue_floor": transform.eigenvalue_floor,
            "training_digest": transform.training_digest,
            "model": metadata["model"],
            "pooling": metadata["pooling"],
        },
        "raw": {
            "pairwise_cosine": pairwise(raw_test),
            "anchor_codec": _codec_metrics(raw_test, raw_anchors),
        },
        "whitened": {
            "pairwise_cosine": pairwise(white_test),
            "anchor_codec": _codec_metrics(white_test, white_anchors),
        },
        "interpretation": (
            "This measures held-out anchor reconstruction and geometry only. "
            "It does not establish an ordinary-retrieval improvement without "
            "a labelled relevance corpus."
        ),
    }, transform


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fit-corpus", action="append", default=[],
        help="public document used to fit the transform; repeatable",
    )
    parser.add_argument(
        "--test-corpus", default=str(ROOT / "docs" / "ARCHITECTURE.md"),
        help="separate public document used only for evaluation",
    )
    parser.add_argument("--fit-limit", type=int, default=96)
    parser.add_argument("--test-limit", type=int, default=48)
    parser.add_argument("--shrinkage", type=float, default=0.10)
    parser.add_argument("--eigenvalue-floor", type=float, default=1e-6)
    parser.add_argument("--save-transform", help="optional SABLEWHITE1 output path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    fit_paths = args.fit_corpus or [str(ROOT / "docs" / "THE_STORY_OF_SABLE.md")]
    result, transform = run(
        fit_paths, args.test_corpus, args.fit_limit, args.test_limit,
        args.shrinkage, args.eigenvalue_floor,
    )
    if args.save_transform:
        white.save(transform, args.save_transform)
        result["transform"]["saved_to"] = args.save_transform
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"fit: {result['fit']['chunks']} chunks")
        print(f"test: {result['test']['chunks']} chunks")
        print(f"transform: {result['transform']['dimensions']}d, "
              f"shrinkage {result['transform']['shrinkage']:.3f}")
        print("\nanchor reconstruction on held-out vectors")
        print(f"{'form':<12} {'mean cosine':>12} {'worst':>8} "
              f"{'recovered@1':>13} {'median rank':>12}")
        print("-" * 66)
        for name in ("raw", "whitened"):
            row = result[name]["anchor_codec"]
            print(f"{name:<12} {row['mean_cosine']:>12.4f} "
                  f"{row['worst_cosine']:>8.4f} "
                  f"{row['recovered_at_1']:>12.0%} "
                  f"{row['median_rank']:>12}")
        for name in ("raw", "whitened"):
            row = result[name]["pairwise_cosine"]
            print(f"{name:<12} held-out pairwise cosine "
                  f"{row['mean']:+.4f} +/- {row['standard_deviation']:.4f}")
        print("\n" + result["interpretation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
