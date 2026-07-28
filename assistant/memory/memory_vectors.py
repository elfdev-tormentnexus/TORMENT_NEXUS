"""
Turns the memory store into fixed-width vectors for the retrieval panel.

The panel projects one vector per memory. These are built from exactly the
tokens `memory_logic.select_relevant()` ranks on, because the panel's whole
claim is that it shows the retrieval this project actually performs. Feeding
it a richer representation than the retrieval uses would draw an accurate
picture of a system that is not running.

That also makes the failure mode visible rather than described: retrieval is
literal word overlap, so a memory phrased "the T-Deck mesh transmitter" shares
no token with a question about "the radio" and is filtered out before ranking
ever happens. Those memories have no neighbours to be pulled toward, and the
projection strands them at the edge of the cloud where they can be counted.

Tokens are hashed into a fixed number of buckets rather than given a column
each. A column per token makes the projection's cost grow with how much the
operator has ever said, and the projection is O(dimensions) per memory per
power-iteration step -- 24 steps, three components. crc32 rather than hash()
because hash() is salted per process, which would relayout the cloud on every
restart for no reason the operator could see.
"""

import zlib


DIMENSIONS = 64


def _bucket(token, dimensions):
    return zlib.crc32(token.encode("utf-8", "replace")) % dimensions


def vectors(memories, dimensions=DIMENSIONS):
    """One L2-normalised vector per memory, in the order given."""
    from memory import memory_logic

    built = []

    for item in memories:
        vector = [0.0] * dimensions

        for token in memory_logic.tokens(item.get("memory", "")):
            vector[_bucket(token, dimensions)] += 1.0

        # Normalised so the projection reflects which words a memory uses
        # rather than how many. score() already divides by the memory's own
        # token count for the same reason.
        length = sum(value * value for value in vector) ** 0.5

        if length:
            vector = [value / length for value in vector]

        built.append(vector)

    return built


def isolated(memories):
    """
    Indices of memories sharing no token with any other memory.

    These are unreachable by design, not by accident: retrieval keeps only
    memories whose tokens intersect the query, so a memory that overlaps
    nothing in the store can still be retrieved by a query that happens to
    quote it, and by nothing else. The count is the honest measure of how
    much the word-overlap approach is costing.
    """
    from memory import memory_logic

    token_sets = [
        memory_logic.tokens(item.get("memory", ""))
        for item in memories
    ]
    alone = []

    for index, own in enumerate(token_sets):
        if not own:
            alone.append(index)
            continue

        if not any(
            own & other
            for position, other in enumerate(token_sets)
            if position != index
        ):
            alone.append(index)

    return alone
