"""A rosetta stone between two embedding models' vector spaces.

Two agents built on different embedders cannot share vectors. Dimension 7
in one model has no relationship to dimension 7 in another, same
dimensionality does not imply same meaning, and cosine across two spaces is
noise rather than degraded signal. A container format cannot fix that: it
transports numbers faithfully and says nothing about what they mean.

What does address it is a shared set of anchor texts. Each model embeds the
same anchors in its own private space, and any vector is then re-expressed
as its similarities to those anchors instead of its own coordinates. Both
models end up describing meaning in a coordinate system defined by content
they both saw. The analogy is exact rather than decorative -- the stone
worked because the same decree appeared in three scripts.

Prior art, stated first: this is *relative representations* (Moschella et
al., "Relative representations enable zero-shot latent space
communication", ICLR 2023). The older alternative is a learned linear map
(Procrustes; Mikolov 2013, Conneau 2017), which works but must be fitted
per model pair from paired data. Relative representations need no fitting,
which is what makes them usable between agents that meet without prior
arrangement.

This module builds the stone and translates with it. It does not claim the
translation is good -- run `measure` for that, against two real embedders.

    python tools/rosetta_stone.py build --url http://127.0.0.1:8082 --out stone.json
    python tools/rosetta_stone.py measure --a http://127.0.0.1:8082 --b http://127.0.0.1:8083
"""
import argparse
import hashlib
import json
import math
import os
import sys

import requests

MAGIC = "SABLEROSETTA1"

# --- The anchors ------------------------------------------------------
#
# These are the shared decree. Both models must embed the identical ordered
# list or the resulting coordinates are not comparable, which is why the
# digest below is checked rather than trusted.
#
# The core is deliberately general. Anchors must span the domain they will
# be used on, and a stone meant for an agent whose subject matter is unknown
# cannot assume that subject matter. Too few anchors and distinct meanings
# collapse into the same coordinates; the published work uses hundreds.

ANCHOR_CORE_V1 = [
    "a cat sleeping in a patch of sunlight",
    "the price of bread rose again this year",
    "he apologised, but did not mean it",
    "water boils at one hundred degrees celsius",
    "the train was forty minutes late",
    "she solved the equation on the third attempt",
    "a funeral on a cold morning",
    "the server returned an unexpected error",
    "children playing football in the street",
    "an argument about money between old friends",
    "the mountain range seen from the air",
    "a recipe for bread with too few instructions",
    "the court dismissed the case without comment",
    "how a combustion engine converts fuel to motion",
    "a love letter never sent",
    "the election result surprised nobody",
    "rust forming on an abandoned bicycle",
    "a doctor explaining a diagnosis carefully",
    "the difference between weather and climate",
    "someone laughing at a joke they did not understand",
    "a contract with an ambiguous clause",
    "the smell of rain on hot pavement",
    "debugging a program at two in the morning",
    "a river flooding its banks in spring",
    "the loneliness of a hotel room",
    "instructions for assembling a wooden chair",
    "a language with no word for blue",
    "the stock market fell sharply on Tuesday",
    "grandparents telling the same story again",
    "how vaccines train the immune system",
    "a bridge closed for structural repairs",
    "an apology accepted but not forgotten",
    "the rules of a game nobody remembers inventing",
    "photosynthesis in a leaf",
    "a city at night from a high window",
    "the tax form asks for information twice",
    "a dog waiting by the door",
    "two theories that cannot both be true",
    "the harvest failed for the second year",
    "encrypting a message so only one person can read it",
    "an old photograph of people whose names are lost",
    "the difference between a promise and a prediction",
    "a surgeon washing their hands",
    "wind turbines on a distant ridge",
    "someone reading a map upside down",
    "the first day at a new school",
    "a proof that requires no diagram",
    "coffee gone cold during a long meeting",
    "the migration of birds in autumn",
    "a warning label nobody reads",
    "the moment before a difficult conversation",
    "how compound interest accumulates over decades",
    "a violin out of tune",
    "the border between two countries at war",
    "salt dissolving in warm water",
    "an inherited house full of someone else's furniture",
    "the algorithm sorted the list in place",
    "a child asking why repeatedly",
    "erosion carving a canyon over millennia",
    "the meeting ended without a decision",
    "bees navigating by the position of the sun",
    "a translation that loses the joke",
    "the engine made a noise it should not make",
    "forgiveness offered before it was asked for",
    "measuring the distance to a star",
    "a queue that has stopped moving",
    "the last train home",
    "antibiotic resistance spreading in a hospital",
    "a song that means something different now",
    "the committee voted to delay the vote",
    "concrete cracking in a hard frost",
    "someone lying convincingly",
    "the difference between weight and mass",
    "an empty theatre after the audience leaves",
    "a password written on a sticky note",
    "the tide going out further than expected",
    "learning to ride a bicycle by falling",
    "a legal system that is slow but not corrupt",
    "the chemistry of bread rising",
    "grief arriving months later",
    "a satellite losing contact with the ground",
    "the ethics of an experiment on animals",
    "a wall painted over many times",
    "counting votes by hand",
    "the physics of a spinning top",
    "an interview where both people are performing",
    "seeds surviving a fire",
    "the backup was never tested",
    "a border collie herding sheep",
    "inflation explained badly",
    "the silence after a loud noise",
    "a knot that holds under load",
    "someone changing their mind in public",
    "the geology of a coastline",
    "an argument that is valid but unsound",
    "hospital corridors at three in the morning",
    "a machine that learns from its mistakes",
    "the taste of food from childhood",
    "a village with no remaining young people",
    "encryption keys stored insecurely",
    "the aerodynamics of a paper aeroplane",
    "a debt forgiven",
    "clouds forming over warm ocean water",
    "a joke that only works out loud",
    "the difference between data and evidence",
    "someone practising scales badly",
    "an old road no longer on any map",
    "the immune response to a splinter",
    "a decision made by not deciding",
    "light bending through water",
    "the smell of a hardware store",
    "a promise made to a dying person",
    "population growth slowing unexpectedly",
    "a fire alarm during an exam",
    "the mechanics of a door hinge",
    "someone remembering a face but not a name",
    "sediment layers recording past floods",
    "an apology that makes things worse",
    "the mathematics of a fair division",
    "a shipping container lost at sea",
    "learning a language as an adult",
    "the failure mode nobody planned for",
]

# The project extension. Optional, and carried under its own digest so an
# outside agent that has none of this material can use the core alone.
ANCHOR_PROJECT_V1 = [
    "a local language model running without a network connection",
    "an assistant that edits its own source under review",
    "refusal behaviour deliberately weakened in a released model",
    "embeddings quantised from float32 to uint8",
    "a checksum that fails rather than returning junk",
    "an offline reference library searched by exact words",
    "a guard that fails closed when it cannot decide",
    "hardware that senses movement but cannot identify a person",
    "a release archive split into numbered parts",
    "conversation memory the operator can inspect and delete",
    "a test that passes even with the bug reinstated is worthless",
    "publishing a failed experiment rather than tuning it into agreement",
    "an agent interface restricted to loopback",
    "voice synthesis running entirely on the local machine",
    "a container format that declares its own layout",
    "the difference between a container and a compression",
]


def anchor_digest(texts):
    """Identity of an ordered anchor list. Order is part of the meaning."""
    h = hashlib.sha256()
    for t in texts:
        h.update(t.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


# --- Talking to an embedding server -----------------------------------

def embed(texts, url, api_key=None, batch=32, timeout=120):
    """Embed texts through a llama.cpp --embedding server."""
    out = []
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        r = requests.post(url.rstrip("/") + "/v1/embeddings",
                          headers=headers, json={"input": chunk},
                          timeout=timeout)
        r.raise_for_status()
        rows = r.json()["data"]
        rows.sort(key=lambda d: d.get("index", 0))
        out.extend(d["embedding"] for d in rows)
    if len(out) != len(texts):
        raise ValueError(f"asked for {len(texts)} vectors, got {len(out)}")
    return out


def model_identity(url, api_key=None, timeout=10):
    """Whatever the server calls the model it is serving."""
    headers = {}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    try:
        r = requests.get(url.rstrip("/") + "/v1/models",
                         headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json().get("data") or []
        if data:
            return str(data[0].get("id", "unknown"))
    except Exception:
        pass
    return "unknown"


# --- Vector arithmetic, stdlib only -----------------------------------

def norm(v):
    return math.sqrt(sum(x * x for x in v)) or 1.0


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / (norm(a) * norm(b))


def to_relative(vectors, anchor_vectors):
    """Re-express each vector as its similarities to the anchors.

    This is the whole trick. The output no longer lives in the model's own
    space; it lives in a space whose axes are meanings both models saw.
    """
    return [[cosine(v, a) for a in anchor_vectors] for v in vectors]


def neighbours(vectors, k):
    """Top-k nearest index list for each row, excluding the row itself."""
    out = []
    for i, v in enumerate(vectors):
        scored = [(cosine(v, w), j) for j, w in enumerate(vectors) if j != i]
        scored.sort(reverse=True)
        out.append([j for _, j in scored[:k]])
    return out


def spearman(xs, ys):
    """Rank correlation, no scipy."""
    def rank(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        r = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for t in range(i, j + 1):
                r[order[t]] = avg
            i = j + 1
        return r

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx)
                    * sum((b - my) ** 2 for b in ry)) or 1.0
    return num / den


# --- The stone --------------------------------------------------------

def build_stone(url, api_key=None, include_project=True):
    """One side of the stone: this model's reading of the shared anchors.

    The stone is one-sided by design. It carries the anchor texts so the
    other agent can embed them itself, plus this model's own anchor
    vectors so a reader can see what this side looks like. The other agent
    supplies its half; nothing here needs to know anything about it.
    """
    anchors = list(ANCHOR_CORE_V1)
    project = list(ANCHOR_PROJECT_V1) if include_project else []
    vectors = embed(anchors + project, url, api_key)
    return {
        "magic": MAGIC,
        "model": model_identity(url, api_key),
        "pooling": "mean",
        "dims": len(vectors[0]),
        "core_digest": anchor_digest(anchors),
        "core_count": len(anchors),
        "project_digest": anchor_digest(project) if project else None,
        "project_count": len(project),
        "anchors_core": anchors,
        "anchors_project": project,
        "anchor_vectors": vectors,
        "note": ("Relative representations, Moschella et al. ICLR 2023. "
                 "Compare only against a stone with a matching core_digest."),
    }


class AnchorMismatch(Exception):
    """Two stones that do not share a decree cannot translate."""


def check_compatible(stone_a, stone_b, require_project=False):
    """Refuse rather than return a number that looks like a similarity."""
    for s in (stone_a, stone_b):
        if s.get("magic") != MAGIC:
            raise AnchorMismatch(f"not a rosetta stone: {s.get('magic')!r}")
    if stone_a["core_digest"] != stone_b["core_digest"]:
        raise AnchorMismatch(
            "core anchor digests differ -- these stones describe different "
            f"decrees ({stone_a['core_digest'][:12]} vs "
            f"{stone_b['core_digest'][:12]}); comparison would be noise")
    if require_project:
        if stone_a.get("project_digest") != stone_b.get("project_digest"):
            raise AnchorMismatch("project anchor digests differ")
    return True


def translate(vectors, stone, use_project=False):
    """Absolute vectors from stone's model -> shared relative space."""
    n = stone["core_count"] + (stone["project_count"] if use_project else 0)
    return to_relative(vectors, stone["anchor_vectors"][:n])


# --- CLI --------------------------------------------------------------

# The embedding servers run with -c 512, and a sentence embedder is not
# meant to see long inputs anyway. Truncating here keeps a long paragraph
# from failing the whole run; both models see the identical truncation, so
# the comparison stays fair.
MAX_CHARS = 800


def _corpus(path, limit=None):
    """Paragraph chunks, the same shape the research doc measured."""
    text = open(path, encoding="utf-8").read()
    parts = [p.strip().replace("\n", " ") for p in text.split("\n\n")]
    parts = [p[:MAX_CHARS] for p in parts if len(p) > 40]
    return parts[:limit] if limit else parts


def cmd_build(args):
    stone = build_stone(args.url, args.key, not args.core_only)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(stone, fh)
    print(f"stone written: {args.out}")
    print(f"  model        : {stone['model']}")
    print(f"  dims         : {stone['dims']}")
    print(f"  core anchors : {stone['core_count']}  "
          f"digest {stone['core_digest'][:16]}")
    print(f"  project      : {stone['project_count']}")
    print(f"  bytes        : {os.path.getsize(args.out)}")


def cmd_measure(args):
    corpus = _corpus(args.corpus, args.limit)
    print(f"corpus: {len(corpus)} chunks from {args.corpus}\n")

    print("building both sides of the stone...")
    stone_a = build_stone(args.a, args.a_key, not args.core_only)
    stone_b = build_stone(args.b, args.b_key, not args.core_only)
    check_compatible(stone_a, stone_b)
    print(f"  A: {stone_a['model']}  {stone_a['dims']}d")
    print(f"  B: {stone_b['model']}  {stone_b['dims']}d")
    print(f"  shared core digest {stone_a['core_digest'][:16]}  "
          f"({stone_a['core_count']} anchors)\n")

    abs_a = embed(corpus, args.a, args.a_key)
    abs_b = embed(corpus, args.b, args.b_key)
    rel_a = translate(abs_a, stone_a, args.use_project)
    rel_b = translate(abs_b, stone_b, args.use_project)

    # Does the translation preserve each model's own neighbour structure?
    pairs = [(i, j) for i in range(len(corpus)) for j in range(i + 1, len(corpus))]
    for name, absv, relv in (("A", abs_a, rel_a), ("B", abs_b, rel_b)):
        xs = [cosine(absv[i], absv[j]) for i, j in pairs]
        ys = [cosine(relv[i], relv[j]) for i, j in pairs]
        print(f"within-model fidelity {name}: spearman(absolute, relative) "
              f"= {spearman(xs, ys):+.4f}")

    # The actual question: do the two models agree about neighbours once
    # they are speaking the same language?
    k = args.k
    na, nb = neighbours(rel_a, k), neighbours(rel_b, k)
    overlap = sum(len(set(x) & set(y)) for x, y in zip(na, nb)) / (len(na) * k)

    native_a, native_b = neighbours(abs_a, k), neighbours(abs_b, k)
    native = sum(len(set(x) & set(y)) for x, y in zip(native_a, native_b)) / (len(na) * k)

    chance = k / max(1, len(corpus) - 1)

    print(f"\ntop-{k} neighbour agreement between the two models")
    print(f"  in relative space (translated) : {overlap:.3f}")
    print(f"  each model's native neighbours : {native:.3f}   "
          f"<- ceiling: how much they agree at all")
    print(f"  chance                         : {chance:.3f}")
    print("\nNote: the models' absolute spaces cannot be compared directly at "
          f"all ({stone_a['dims']}d vs {stone_b['dims']}d). The native figure "
          "is each model's own\nneighbour list compared by index, which is the "
          "ceiling any translation could reach.")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="write this model's side of the stone")
    b.add_argument("--url", required=True)
    b.add_argument("--key")
    b.add_argument("--out", default="rosetta_stone.json")
    b.add_argument("--core-only", action="store_true")
    b.set_defaults(func=cmd_build)

    m = sub.add_parser("measure", help="does translation survive between two models")
    m.add_argument("--a", required=True, help="embedding server A")
    m.add_argument("--b", required=True, help="embedding server B")
    m.add_argument("--a-key")
    m.add_argument("--b-key")
    m.add_argument("--corpus", default="docs/THE_STORY_OF_SABLE.md")
    m.add_argument("--limit", type=int, default=None)
    m.add_argument("--k", type=int, default=5)
    m.add_argument("--core-only", action="store_true")
    m.add_argument("--use-project", action="store_true")
    m.set_defaults(func=cmd_measure)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
