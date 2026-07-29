"""Test whether whitening improves Rosetta's cross-model anchor bridge.

This is a held-out research harness, not a revision of SABLEROSETTA1.  Each
model receives its own regularised ZCA transform fitted on the *same declared
reference texts*.  It then transforms both that model's held-out vectors and
its copy of the shared anchors before ordinary relative representations are
made.  The resulting coordinates remain comparable by anchor index; native
coordinates never are.

No variant is selected by this tool.  It reports raw, anchor-centred,
whitened, and whitened-plus-anchor-centred controls on the same held-out text.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "assistant"))
sys.path.insert(0, str(ROOT / "tools"))

import rosetta_stone as rosetta  # noqa: E402
import vector_whitening as white  # noqa: E402


MAX_CHARS = 800


def _chunks(path, limit=None):
    """Public paragraph chunks, bounded identically for both models."""
    text = Path(path).read_text(encoding="utf-8")
    rows = [part.strip().replace("\n", " ") for part in text.split("\n\n")]
    rows = [row[:MAX_CHARS] for row in rows if len(row) > 120]
    return rows[:limit] if limit else rows


def _document_digest(paths, chunks):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(Path(path).as_posix()).encode("utf-8"))
        digest.update(b"\x00")
    for chunk in chunks:
        digest.update(chunk.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


def _anchor_centred(vectors, anchors):
    """Remove one model's anchor mean without changing the anchor axes."""
    if not anchors:
        raise ValueError("the shared anchor list cannot be empty")
    dimensions = len(anchors[0])
    if any(len(row) != dimensions for row in anchors):
        raise ValueError("anchor vectors do not share a dimension")
    mean = [sum(row[index] for row in anchors) / len(anchors)
            for index in range(dimensions)]
    return [[value - centre for value, centre in zip(row, mean)]
            for row in vectors], [[value - centre for value, centre in zip(row, mean)]
                          for row in anchors]


def _neighbour_agreement(left, right, k):
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("both sides need the same two or more held-out rows")
    if not 1 <= k < len(left):
        raise ValueError("k must be between one and held-out rows minus one")
    neighbours_left = rosetta.neighbours(left, k)
    neighbours_right = rosetta.neighbours(right, k)
    overlap = sum(len(set(a) & set(b))
                  for a, b in zip(neighbours_left, neighbours_right))
    return overlap / (len(left) * k)


def _fidelity(absolute, relative):
    pairs = [(i, j) for i in range(len(absolute))
             for j in range(i + 1, len(absolute))]
    raw = [rosetta.cosine(absolute[i], absolute[j]) for i, j in pairs]
    translated = [rosetta.cosine(relative[i], relative[j]) for i, j in pairs]
    return rosetta.spearman(raw, translated)


def _relative(vectors, anchors):
    return rosetta.to_relative(vectors, anchors)


def _variant(name, test_a, test_b, anchors_a, anchors_b, raw_a, raw_b, k,
             transforms=None):
    """Measure one same-anchor geometry against the unchanged native ceiling."""
    relative_a = _relative(test_a, anchors_a)
    relative_b = _relative(test_b, anchors_b)
    agreement = _neighbour_agreement(relative_a, relative_b, k)
    native = _neighbour_agreement(raw_a, raw_b, k)
    return {
        "name": name,
        "neighbour_agreement": agreement,
        "native_ceiling": native,
        "ceiling_fraction": agreement / native if native else None,
        "within_model_fidelity": {
            "a": _fidelity(raw_a, relative_a),
            "b": _fidelity(raw_b, relative_b),
        },
        "transform_digests": transforms or {},
    }


def evaluate(fit_a, fit_b, test_a, test_b, anchors_a, anchors_b, *,
             metadata_a, metadata_b, shrinkages=(0.02, 0.10, 0.30), k=5):
    """Pure held-out comparison; all inputs are vectors already in memory."""
    if len(fit_a) != len(fit_b):
        raise ValueError("the two models must fit the same count of texts")
    if len(test_a) != len(test_b):
        raise ValueError("the two models must test the same count of texts")
    if len(fit_a) < 2:
        raise ValueError("at least two fit vectors are required")

    rows = []
    centred_test_a, centred_anchors_a = _anchor_centred(test_a, anchors_a)
    centred_test_b, centred_anchors_b = _anchor_centred(test_b, anchors_b)
    rows.append(_variant("raw", test_a, test_b, anchors_a, anchors_b,
                         test_a, test_b, k))
    rows.append(_variant("anchor-centred", centred_test_a, centred_test_b,
                         centred_anchors_a, centred_anchors_b,
                         test_a, test_b, k))

    for shrinkage in shrinkages:
        transform_a = white.fit(fit_a, shrinkage=shrinkage, metadata=metadata_a)
        transform_b = white.fit(fit_b, shrinkage=shrinkage, metadata=metadata_b)
        transformed_test_a = transform_a.transform_many(test_a, normalise=True)
        transformed_test_b = transform_b.transform_many(test_b, normalise=True)
        transformed_anchors_a = transform_a.transform_many(
            anchors_a, normalise=True)
        transformed_anchors_b = transform_b.transform_many(
            anchors_b, normalise=True)
        transforms = {
            "a": transform_a.document()["digest"],
            "b": transform_b.document()["digest"],
            "shrinkage": shrinkage,
        }
        rows.append(_variant(
            f"zca-{shrinkage:.2f}", transformed_test_a, transformed_test_b,
            transformed_anchors_a, transformed_anchors_b, test_a, test_b, k,
            transforms,
        ))
        centred_test_a, centred_anchors_a = _anchor_centred(
            transformed_test_a, transformed_anchors_a)
        centred_test_b, centred_anchors_b = _anchor_centred(
            transformed_test_b, transformed_anchors_b)
        rows.append(_variant(
            f"zca-{shrinkage:.2f}-anchor-centred",
            centred_test_a, centred_test_b, centred_anchors_a,
            centred_anchors_b, test_a, test_b, k, transforms,
        ))
    return rows


def run(fit_paths, test_paths, url_a, url_b, *, a_key=None, b_key=None,
        fit_limit=None, test_limit=None, shrinkages=(0.02, 0.10, 0.30), k=5):
    """Embed a declared split and compare bridge geometries on held-out text."""
    fit_chunks = []
    for path in fit_paths:
        fit_chunks.extend(_chunks(path, fit_limit))
    test_chunks = []
    for path in test_paths:
        test_chunks.extend(_chunks(path, test_limit))
    if len(fit_chunks) < 2 or len(test_chunks) < 2:
        raise ValueError("fit and held-out corpora each need at least two chunks")

    stone_a = rosetta.build_stone(url_a, a_key)
    stone_b = rosetta.build_stone(url_b, b_key)
    rosetta.check_compatible(stone_a, stone_b)
    fit_a = rosetta.embed(fit_chunks, url_a, a_key)
    fit_b = rosetta.embed(fit_chunks, url_b, b_key)
    test_a = rosetta.embed(test_chunks, url_a, a_key)
    test_b = rosetta.embed(test_chunks, url_b, b_key)

    document_digest = _document_digest(fit_paths, fit_chunks)
    common = {
        "pooling": "mean",
        "reference_documents": [str(Path(path).as_posix()) for path in fit_paths],
        "reference_document_digest": document_digest,
        "rosetta_core_digest": stone_a["core_digest"],
        "rosetta_coordinate_count": stone_a["core_count"],
    }
    metadata_a = {**common, "model": stone_a["model"]}
    metadata_b = {**common, "model": stone_b["model"]}
    rows = evaluate(
        fit_a, fit_b, test_a, test_b,
        stone_a["anchor_vectors"][:stone_a["core_count"]],
        stone_b["anchor_vectors"][:stone_b["core_count"]],
        metadata_a=metadata_a, metadata_b=metadata_b,
        shrinkages=shrinkages, k=k,
    )
    return {
        "experiment": "held-out model-specific whitening for Rosetta anchors",
        "fit": {
            "documents": [str(Path(path).as_posix()) for path in fit_paths],
            "chunks": len(fit_chunks),
            "document_digest": document_digest,
        },
        "held_out": {
            "documents": [str(Path(path).as_posix()) for path in test_paths],
            "chunks": len(test_chunks),
        },
        "models": {
            "a": {"identity": stone_a["model"], "dimensions": stone_a["dims"]},
            "b": {"identity": stone_b["model"], "dimensions": stone_b["dims"]},
            "core_anchor_digest": stone_a["core_digest"],
            "core_anchor_count": stone_a["core_count"],
        },
        "k": k,
        "variants": rows,
        "interpretation": (
            "A positive result must improve held-out relative-space neighbour "
            "agreement over the raw control. It remains a bridge measurement, "
            "not proof that either model's ordinary retrieval improved."
        ),
    }


@contextmanager
def _temporary_local_server(url, model_path):
    """Start one authenticated loopback embedder for a local experiment."""
    from core.config import LLAMA_SERVER, MODEL_API_KEY, MODEL_API_KEY_FILE

    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the temporary experiment server must be loopback-only")
    arguments = [
        LLAMA_SERVER, "-m", model_path, "--embedding", "--pooling", "mean",
        "--alias", "rosetta-nomic-whitening", "-c", "512", "-ub", "512",
        "--host", parsed.hostname or "127.0.0.1", "--port",
        str(parsed.port or 8083), "-ngl", "0", "-t", "2",
    ]
    if MODEL_API_KEY_FILE:
        arguments.extend(("--api-key-file", MODEL_API_KEY_FILE))
    else:
        arguments.extend(("--api-key", MODEL_API_KEY))
    process = subprocess.Popen(
        arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                import requests
                response = requests.get(url.rstrip("/") + "/health",
                                        headers={"Authorization": "Bearer " + MODEL_API_KEY},
                                        timeout=2)
                if response.status_code == 200:
                    yield MODEL_API_KEY
                    return
            except Exception:
                pass
            if process.poll() is not None:
                break
            time.sleep(0.5)
        raise RuntimeError("the temporary Nomic embedding server did not start")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--a", default="http://127.0.0.1:8082")
    parser.add_argument("--b", default="http://127.0.0.1:8083")
    parser.add_argument("--fit-corpus", action="append", required=True)
    parser.add_argument("--test-corpus", action="append", required=True)
    parser.add_argument("--fit-limit", type=int)
    parser.add_argument("--test-limit", type=int)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--shrinkage", action="append", type=float)
    parser.add_argument("--use-local-key", action="store_true",
                        help="read the local loopback key without exposing it")
    parser.add_argument("--start-b-model",
                        help="temporarily start this local model on --b")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    key = None
    if args.use_local_key or args.start_b_model:
        from core.config import MODEL_API_KEY
        key = MODEL_API_KEY
    if args.start_b_model:
        with _temporary_local_server(args.b, args.start_b_model) as b_key:
            result = run(args.fit_corpus, args.test_corpus, args.a, args.b,
                         a_key=key, b_key=b_key, fit_limit=args.fit_limit,
                         test_limit=args.test_limit,
                         shrinkages=args.shrinkage or (0.02, 0.10, 0.30),
                         k=args.k)
    else:
        result = run(args.fit_corpus, args.test_corpus, args.a, args.b,
                     a_key=key, b_key=key, fit_limit=args.fit_limit,
                     test_limit=args.test_limit,
                     shrinkages=args.shrinkage or (0.02, 0.10, 0.30),
                     k=args.k)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"fit: {result['fit']['chunks']} chunks")
        print(f"held out: {result['held_out']['chunks']} chunks")
        print(f"models: {result['models']['a']['dimensions']}d / "
              f"{result['models']['b']['dimensions']}d")
        print("\nheld-out bridge agreement")
        print(f"{'variant':<28} {'agreement':>10} {'ceiling':>9} {'fraction':>10} "
              f"{'fidelity A/B':>17}")
        print("-" * 82)
        for row in result["variants"]:
            fidelity = row["within_model_fidelity"]
            fraction = row["ceiling_fraction"]
            print(f"{row['name']:<28} {row['neighbour_agreement']:>10.3f} "
                  f"{row['native_ceiling']:>9.3f} {fraction:>9.0%} "
                  f"{fidelity['a']:>+7.3f}/{fidelity['b']:>+7.3f}")
        print("\n" + result["interpretation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
