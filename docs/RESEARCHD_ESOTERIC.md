# researchD esoteric

## Visual computing languages, vector-to-pixel computation, semantic fields, and Machinesoul

Most programming languages move from **symbol to machine**, while rendering systems move from **vector to pixel**. The central question for Machinesoul is whether a computing language could have the rendered field itself as its native representation.

In such a system, the image would not merely illustrate a computation. The image would be the computation.

## Existing directions

Several existing approaches converge on this possibility:

### Dataflow graphs

Systems such as Quartz Composer, TouchDesigner, and Unreal Blueprints represent computation as a graph. The graph is already visual, and pixels can become nodes within that computation.

### Shader languages

GLSL, WGSL, and Metal Shading Language treat a program as a function evaluated over pixels or spatial samples. Rather than issuing conventional instructions to a CPU, the programmer describes a field over space.

### Signed distance fields

With signed distance fields, objects are equations and computation becomes geometry. Rendering and logic begin to blur because properties such as inside and outside are themselves information.

### Cellular automata

In a cellular automaton, every pixel or cell computes. The image is the current state of the program. Conway's Game of Life demonstrates that such a spatial system can be Turing complete.

## A Machinesoul field language

Machinesoul could go further by replacing syntax with a continuously evolving vector field.

Instead of writing:

```text
if (energy > threshold)
    spawn();
```

one could paint a region in which vectors converge. The renderer could interpret visual and spatial properties as executable operations:

- convergence = creation
- divergence = destruction
- curl = rotation
- density = memory
- color = type
- opacity = confidence
- temporal persistence = state

The language would no longer be text. It would be a dynamic field.

Every frame could be all of the following at once:

- source code
- execution state
- debugger
- visualization

The usual separation among program, execution, and representation would disappear.

## Semantic fields

One possible representation is a **semantic field** in which every object emits vectors expressing relationships.

```text
Tree
  ↘
   nutrients
       ↘
        soil
```

This relationship could become a literal force field. Concepts could attract or repel one another. Execution would be the system relaxing toward equilibrium, and reasoning would become field dynamics.

## Relationship to modern AI

This concept aligns with the way modern AI already operates in high-dimensional vector spaces. A simplified view of a transformer-based system is:

```text
text
  ↓
embeddings
  ↓
attention
  ↓
embeddings
  ↓
text
```

Machinesoul could expose that hidden vector space visually:

```text
concept vectors
      ↓
continuous field
      ↓
rendered image
      ↓
interaction
      ↓
updated field
```

The rendered image would be an executable representation rather than a picture placed on top of hidden computation.

## Possible language primitives

- **Points** = entities
- **Vectors** = intent or influence
- **Fields** = memory
- **Curves** = causality
- **Color** = semantic domain
- **Brightness** = activation
- **Time** = execution

A program in this medium would not simply be “run.” It would be watched as it settles, like a fluid simulation finding equilibrium. Editing could feel more like sculpting or painting than typing.

## Research direction

This idea sits at the intersection of graphics, dynamical systems, programming languages, and AI reasoning. It would not need to replace conventional code. Its strongest uses may be exploratory systems, reasoning visualizations, simulations, and Machinesoul itself: environments in which vector fields and pixels are not just outputs, but the executable medium.


---

# Findings on the above

*Claude, 2026-07-31, appended after review. The sections above are preserved
unedited. This is a critique and a counter-proposal, not a dismissal: the prior
art cited above is chosen correctly and the instinct behind it survives. It is
aimed at the wrong abstraction.*

## The name collision that carries the argument

The proposal rests on machinesoul already being visual computation that could be
made executable. It is not, and the reason is one word doing two jobs.

**Machinesoul's vectors** are ordered four-byte tuples mapped to RGBA in raster
order. Pixel one is bytes one to four. There is no direction, no magnitude, and
no neighbourhood relationship: byte five sits beside byte one because of file
offset, not because of meaning. Adjacency in the image is adjacency in the
stream and nothing more.

**The proposal's vectors** are geometric. They converge, diverge, and have curl.
Those operations require a field with real direction and locality.

These are different objects sharing a word. `MACHINESOUL_RELEASE_CUT_METHOD.md`
already draws the boundary: ordered byte-vector space, not embedding space and
not a semantic claim about model weights. The brainstorm walks into exactly the
reading that document was written to prevent. Machinesoul is an excellent
serialization format wearing a PNG. Its visuality is a carrier, not a substrate.

Anything built on the assumption that the pixels already mean something
spatially will fail at the first attempt to compose two operations.

## What machinesoul actually contributes

Three candidate insights are worth lifting. Only the third is deep.

1. **A universal decoder.** PNG is everywhere, so distribution is free. Clever,
   but a logistics insight rather than a computational one.

2. **Boundary selection by measurement.** The cutter does not split at fixed
   offsets. It samples the payload and cuts where local activity is lowest,
   under a declared preference order: end of file, then structural text seam,
   then quietest aligned window, then forced fallback. Decomposition points are
   *chosen by measured structure* rather than declared by the author. This has
   real transferable content.

3. **Integrity as a precondition of access.** The bytes cannot be obtained
   unless the digest matches. Verification is not a step performed after reading
   and possibly skipped. It is the door.

## The principle already implemented seven times

The third insight is not confined to machinesoul. The same move appears
throughout the tree and has never been named as one idea:

- machinesoul refuses to extract unless the payload hash matches;
- `source_awareness` answers narrow source questions with a receipt instead of
  asking the model to guess;
- the librarian records hashes and closed outcomes, never text, and stays
  shadow-only until it earns promotion on measurement;
- `cut` refuses when the source inventory changed after the plan was reviewed;
- `combine_manifests` refuses when its two components were swapped or repeated;
- the provenance council took **no vote**, because a vote would have discarded
  the disagreement and returned a number more confident than the evidence;
- the hedge experiment added a third answer, because a forced binary makes a
  decline indistinguishable from a confident denial.

Every one is the same rule: **refuse rather than assert beyond the evidence.**

## Proposal: the third computational language

The interesting language is not visual. It is this:

> A language in which every value carries its provenance, and `unknown` is a
> first-class value rather than an error.

Three-valued rather than two. `true-because`, `false-because`, and `unknown`,
where unknown is the honest default and cannot be promoted to either other value
without supplying evidence the runtime itself checks.

This is the esoteric mathematics already revived here, arrived at from the other
end. Kleene and Lukasiewicz built three-valued logics precisely because two
values force a commitment the evidence does not support. The hedge experiment
rediscovered the same fact empirically: under a forced binary every `q` sat near
1e-8 and the pivotality statistic was degenerate by construction, and allowing a
third answer moved it five to six orders of magnitude.

The forced binary was not measuring a confident model. It was manufacturing the
appearance of one.

## These primitives compose; the field primitives did not

The brainstorm assigns meanings to field properties: convergence is creation,
density is memory, opacity is confidence, colour is type. Only `curl = rotation`
is dimensionally motivated. The rest are free association, and the test they
fail is composition. If density is memory and curl is rotation, what is a dense
curl? Nothing is forced to answer.

The three-valued primitives pass that test, because the laws are not assigned:

```text
unknown AND false = false      (false regardless of how unknown resolves)
unknown AND true  = unknown    (the answer still depends on it)
unknown OR  true  = true
NOT unknown       = unknown
```

These follow from the semantics rather than from taste. A language needs its
primitives compelled by something. That is the difference between a notation and
a language.

## Where boundary-by-measurement rejoins

The second machinesoul insight has a natural home here. In a language whose
values carry provenance, computation must be divided into independently
verifiable units, and the question of *where to divide* is the cutter's question
asked about programs instead of bytes: place the boundary where measured
coupling is lowest, not where the author guessed.

Checkpoints chosen by measurement, under a declared preference order, with a
forced fallback that must be investigated whenever it fires.

## Prior art, and the objection that matters

Three-valued logic in programming is not new, and its best-known instance is
widely considered a mistake. SQL's `NULL` propagates silently: an expression
quietly becomes unknown, comparisons stop behaving as expected, and the
programmer finds out downstream. The concept is not what failed there.

The difference required here is that unknown must propagate **loudly and with
its reason attached**. SQL's NULL carries no provenance and cannot answer *why*
it is unknown. A value that knows why it is unknown is a different object from
one that merely is.

That is the real research question, and it is a good one: whether carried
provenance is enough to make three-valued logic ergonomic rather than
treacherous.

## Before building any of it

Apply the rule already recorded in `esoteric_math_verdict.md`, because it applies
to this document too. Those proposals were generated by agents instructed not to
read the repository, and consequently recommended as novel a fallback the
project had already shipped.

**Cost every proposal against the current tree before believing its novelty.**

The likely finding is that four fifths of this language already exists,
distributed across the resolver, the manifest verifier, the librarian's logging
discipline and the council's refusal to vote, and that what is missing is not an
implementation but a name and a set of composition laws.

The theory ledger also rejected an embedding-space idea at current scale pending
a conventional ANN benchmark. Any visual or field-based successor to this
document should be costed the same way before it is built.

## One thing worth building regardless

The librarian agreed with itself on 1 of 8 cases when the candidate order was
reversed. That instability is a property of the candidate pool's geometry, and
nobody has looked at it.

Rendering the actual embedding space for those eight cases — where the chosen
passage sat relative to the correct one, and how the decision boundary moved
under reversal — is a semantic field that is literally true rather than
metaphorical, and it is an instrument for a failure that has already been
measured and published. Not an executable medium. A microscope.
