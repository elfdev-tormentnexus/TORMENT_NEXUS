"""Plan the embed selection before spending compute on it.

The shipped researchC field was chosen by a flat per-source round robin under
a global ceiling. With 17,320 sources and a 15,000 ceiling, round one never
completed, so 99.9% of the field is each document's opening chunk and 87% of
the shelf's text has no vector at all. Nothing reported that, because
`library status` measures whether the target was filled, not whether the
target was worth filling.

This is the missing review step, and it is modelled on the release cutter:
inventory the whole corpus, state what a budget would actually buy, and let a
person approve it before it is executed rather than after it is published.

The proposed order is two tiers:

  1. Every source's opening chunk. A document's first chunk is genuinely the
     best routing signal it has, so this is kept deliberately rather than by
     accident -- but it is bounded at one per source instead of consuming
     everything.
  2. Everything else by proportional depth: source_round / source_total. At
     any cut point each source has contributed the same *fraction* of itself,
     so a 35,000-chunk corpus and a 5-chunk corpus are both represented in
     proportion to their size instead of their file count.

Nothing here writes to the database. It reports.
"""

from __future__ import annotations

import collections
import os
import re
import sqlite3
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "assistant"))

import knowledge.library as L  # noqa: E402


DEFAULT_BUDGETS = (15_000, 30_000, 50_000, 75_000)


def corpus_of(path):
    path = path.replace("\\", "/")
    match = re.search(r"user_library/([^/]+)/([^/]+)", path)
    if match:
        return match.group(2)
    return "built-in" if "builtin" in path else "other"


def load(database):
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT c.id, c.ordinal, c.source_id, LENGTH(c.text) AS bytes,
               s.path, s.scope
        FROM chunks c JOIN sources s ON s.id=c.source_id
        """
    ).fetchall()
    connection.close()
    return rows


def order_key(rows):
    """Two-tier key: openings first, then proportional depth."""
    total_per_source = collections.Counter(r["source_id"] for r in rows)
    round_of = {}
    seen = collections.Counter()
    for row in sorted(rows, key=lambda r: (r["source_id"], r["ordinal"], r["id"])):
        seen[row["source_id"]] += 1
        round_of[row["id"]] = seen[row["source_id"]]

    keyed = []
    for row in rows:
        builtin = 0 if row["scope"] == "built-in" else 1
        rnd = round_of[row["id"]]
        if rnd == 1:
            tier, depth = 0, 0.0
        else:
            tier = 1
            depth = rnd / max(total_per_source[row["source_id"]], 1)
        keyed.append((builtin, tier, depth, row["path"], row["id"], row))
    keyed.sort(key=lambda k: (k[0], k[1], k[2], k[3], k[4]))
    return [k[5] for k in keyed]


def report(rows, ordered, budget, shelf_bytes):
    picked = ordered[:budget]
    by_corpus = collections.Counter(corpus_of(r["path"]) for r in picked)
    shelf_corpus = collections.Counter(corpus_of(r["path"]) for r in rows)
    ordinals = collections.Counter(min(r["ordinal"], 3) for r in picked)
    picked_bytes = sum(min(r["bytes"] or 0, L.EMBED_TEXT_BYTE_LIMIT) for r in picked)

    print(f"\n{'='*72}\nBUDGET {budget:,} vectors")
    print(f"{'-'*72}")
    print(f"  text reachable   : {picked_bytes:,} bytes "
          f"({picked_bytes/shelf_bytes*100:.1f}% of shelf)")
    openings = sum(v for k, v in ordinals.items() if k == 0)
    print(f"  opening chunks   : {openings:,} ({openings/len(picked)*100:.1f}%)")
    print(f"  body chunks      : {len(picked)-openings:,} "
          f"({(len(picked)-openings)/len(picked)*100:.1f}%)")
    print(f"  sources covered  : {len({r['source_id'] for r in picked}):,}")
    print(f"\n  {'corpus':<34}{'picked':>9}{'on shelf':>10}{'share':>8}{'of corpus':>11}")
    for name, shelf_n in shelf_corpus.most_common(10):
        got = by_corpus.get(name, 0)
        print(f"  {name[:34]:<34}{got:>9,}{shelf_n:>10,}"
              f"{got/len(picked)*100:>7.1f}%{got/shelf_n*100:>10.1f}%")


def main():
    database = os.path.join(ROOT, "assistant", "knowledge", "library.sqlite3")
    rows = load(database)
    shelf_bytes = sum(r["bytes"] or 0 for r in rows)
    print(f"shelf: {len(rows):,} chunks across "
          f"{len({r['source_id'] for r in rows}):,} sources, "
          f"{shelf_bytes:,} bytes of text")
    print(f"current ceiling: {L.EMBED_GLOBAL_CEILING:,}  "
          f"(below the source count, which is why round one never completes)")

    ordered = order_key(rows)
    budgets = [int(a) for a in sys.argv[1:]] or list(DEFAULT_BUDGETS)
    for budget in budgets:
        report(rows, ordered, min(budget, len(rows)), shelf_bytes)


if __name__ == "__main__":
    main()
