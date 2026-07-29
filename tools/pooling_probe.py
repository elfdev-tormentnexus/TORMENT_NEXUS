"""Determine what the pooled embedder actually does, by reconstruction.

`embedding_server.POOLING_MODE` says "mean", and the comment beside it is
already careful: BGE publishes CLS pooling, and mean is this deployment's
measured choice rather than a claim about how the upstream model trains.
What neither the constant nor the comment establishes is that llama.cpp
*applied* the flag. A configuration value is a request; this asks the
running process.

The method is only available because hazard mode holds two servers. The
unpooled instance returns one vector per token; every candidate pooling is
then a function of those vectors that can be computed here and compared
against what the pooled instance returned for the identical text. A cosine
at 1.0 identifies the pooling; nothing near 1.0 means the server is doing
something none of the candidates describe, which is a finding and not a
failure.

Candidates, and why each is worth ruling out:

    cls          token 0. BGE's published convention.
    mean_all     every token, specials included. llama.cpp's usual reading
                 of --pooling mean.
    mean_inner   specials dropped. sentence-transformers' masked mean, and
                 the one most likely to be confused with mean_all on long
                 text and to diverge on short.
    last         final token. Ruled out for BERT encoders, cheap to check,
                 and the failure mode if a decoder model is ever misplaced
                 into this slot.

Token counts are reported alongside because both servers run with -c 512.
An input that exceeds it is truncated rather than refused, and a truncated
trajectory presented as a whole one is the exact failure this project keeps
saying it will not commit.

    python tools/pooling_probe.py
    python tools/pooling_probe.py --text "one specific sentence to probe"
"""
import argparse
import json
import math
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(ROOT, "assistant", ".model_api_key")

# Both servers are started with -c 512 by their launchers.
CONTEXT_LIMIT = 512

# A reconstruction either is the pooling or it is not. Floating point across
# two processes costs a few units in the last place, not hundredths.
MATCH = 0.9999

PROBES = [
    "a promise made to a dying person",
    "The user likes pineapple pizza.",
    "grief",
    "The train was forty minutes late and nobody complained about it.",
]


def _key(explicit, env_name, default=""):
    if explicit:
        return explicit
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    return default


def _model_key(explicit):
    if explicit:
        return explicit
    value = os.environ.get("TORMENT_NEXUS_MODEL_API_KEY", "").strip()
    if value:
        return value
    try:
        with open(KEY_FILE, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _headers(key):
    return {"Authorization": "Bearer " + key} if key else {}


def cosine(left, right):
    if not left or not right or len(left) != len(right):
        return None
    a = math.sqrt(math.fsum(x * x for x in left))
    b = math.sqrt(math.fsum(x * x for x in right))
    if a <= 0.0 or b <= 0.0:
        return None
    return math.fsum(x * y for x, y in zip(left, right)) / (a * b)


def pooled_vector(url, key, text, timeout=30):
    """One vector from the ordinary embedder, through the OpenAI route."""
    response = requests.post(
        url.rstrip("/") + "/v1/embeddings",
        headers=_headers(key),
        json={"input": [text]},
        timeout=timeout,
    )
    response.raise_for_status()
    rows = response.json()["data"]
    return rows[0]["embedding"]


def token_vectors(url, key, text, timeout=60):
    """Per-token vectors, through llama.cpp's own route.

    /v1/embeddings refuses pooling=none outright, so this deliberately does
    not use the OpenAI-compatible endpoint.
    """
    response = requests.post(
        url.rstrip("/") + "/embeddings",
        headers=_headers(key),
        json={"content": text},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        payload = payload[0]
    embedding = payload.get("embedding") or payload.get("data")
    if not embedding:
        return None
    return embedding if isinstance(embedding[0], list) else [embedding]


def mean_of(vectors):
    if not vectors:
        return None
    width = len(vectors[0])
    return [math.fsum(vector[i] for vector in vectors) / len(vectors)
            for i in range(width)]


def candidates(path):
    """Every pooling that could have produced a single vector from a path."""
    found = {"cls": path[0], "last": path[-1], "mean_all": mean_of(path)}
    # Dropping [CLS] and [SEP] needs at least one token left between them.
    found["mean_inner"] = mean_of(path[1:-1]) if len(path) > 2 else None
    return found


def probe(text, pooled_url, pooled_key, unpooled_url, unpooled_key):
    pooled = pooled_vector(pooled_url, pooled_key, text)
    path = token_vectors(unpooled_url, unpooled_key, text)
    if not path:
        return {"text": text, "error": "no trajectory returned"}

    scores = {name: (cosine(pooled, vector) if vector else None)
              for name, vector in candidates(path).items()}
    ranked = sorted(((score, name) for name, score in scores.items()
                     if score is not None), reverse=True)
    best_score, best_name = ranked[0] if ranked else (None, None)

    return {
        "text": text,
        "tokens": len(path),
        "dimension": len(path[0]),
        "truncated": len(path) >= CONTEXT_LIMIT,
        "scores": scores,
        "verdict": best_name if (best_score or 0.0) >= MATCH else None,
        "best": best_name,
        "best_score": best_score,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pooled", default="http://127.0.0.1:8082")
    parser.add_argument("--unpooled", default="http://127.0.0.1:8084")
    parser.add_argument("--pooled-key", default="")
    parser.add_argument("--unpooled-key", default="")
    parser.add_argument("--text", action="append",
                        help="probe this text; repeatable, replaces defaults")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    pooled_key = _model_key(args.pooled_key)
    unpooled_key = _key(args.unpooled_key,
                        "TORMENT_NEXUS_MACHINESPIRIT_KEY", "machinespirit")

    results = []
    for text in (args.text or PROBES):
        try:
            results.append(probe(text, args.pooled, pooled_key,
                                 args.unpooled, unpooled_key))
        except requests.RequestException as error:
            results.append({"text": text, "error": str(error)})

    if args.json:
        print(json.dumps(results, indent=1))
        return 0

    verdicts = set()
    for row in results:
        if row.get("error"):
            print(f'  {row["text"][:44]!r}  ERROR {row["error"]}')
            continue
        print(f'  {row["text"][:44]!r}')
        print(f'    {row["tokens"]} tokens, {row["dimension"]}-d'
              + ("  TRUNCATED" if row["truncated"] else ""))
        for name, score in sorted(row["scores"].items(),
                                  key=lambda item: -(item[1] or -2)):
            if score is None:
                print(f"    {name:<11} --")
            else:
                print(f"    {name:<11} {score:+.6f}"
                      + ("   <-- match" if score >= MATCH else ""))
        verdicts.add(row["verdict"])

    print()
    if len(verdicts) == 1 and None not in verdicts:
        only = verdicts.pop()
        print(f"The pooled server applies {only} pooling, on every probe.")
        return 0
    if verdicts == {None}:
        print("No candidate reconstructed the pooled vector. The server is "
              "doing something none of these describe.")
        return 1
    print(f"Probes disagreed: {sorted(str(v) for v in verdicts)}. A pooling "
          "that depends on the input is not a pooling.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
