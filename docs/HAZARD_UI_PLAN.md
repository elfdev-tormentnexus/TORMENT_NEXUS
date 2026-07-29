# Plan — the vector panel in hazard mode

Status: **partially built 2026-07-29.** The trajectory overlay is live in
HazardSable only. The step strip, hoverable anchor line, and hazard border
remain planned rather than implied by the overlay.

Goal: when hazard mode is running, the existing retrieval visualisation
should reflect what machinespirit actually measures, instead of showing the
same picture it shows without it.

## What exists, and the rules it already holds

`assistant/ui/vector_panel.py` renders two independent real measurements in
one panel:

- **The cloud** — memories projected to 2D. Position is the first two
  principal components, hue is the third, and **brightness is
  reconstruction fidelity**: a point the projection misrepresents renders
  dim. It shows where it is lying rather than hiding it.
- **The strip** — per-token entropy from the sampler's own distribution.
  Unlike the projection this is not lossy; it is the number the model
  produced.

Three constraints are load-bearing and this plan does not get to relax them.

1. **Pure rendering.** The module never reads files, reaches the network, or
   imports project state, so it can be previewed with
   `python -m ui.vector_panel`. Anything machinespirit adds must be *pushed
   in* by the caller, exactly as `push_token` already works.
2. **No asserted mechanism.** A lit point and a strip column are related by
   sequence, not causation. Nothing in llama.cpp's HTTP API can attribute a
   token to a memory. New marks must not imply one either.
3. **Say where it lies.** Brightness-as-fidelity is the panel's best idea.
   Every addition below must carry the same property or state that it
   cannot.

## What machinespirit makes available

Three measurements the panel does not have today:

| Measurement | Source | Honest? |
| --- | --- | --- |
| Per-token trajectory, 384-d per token | `machinespirit.trajectory()` | Real, not derived |
| Step distance between tokens | cosine between consecutive tokens | Real |
| Nearest anchor concept per token | `machinespirit.trace()` | Real, but the concept comes from a **fixed list**, not from the model |

## Proposed changes

### Implemented: ordered trajectory markers (the conservative version of §1)

`main.py` requests one unpooled trajectory per distinct input only when the
panel is visible, machinespirit is enabled, and the panel has a real semantic
memory frame. It compacts the path through the same fixed semantic projection
as the memory cloud, then `vector_panel.Field` projects it using the cloud's
existing centre, PCA axes, and bounds. The lexical fallback deliberately
draws no path: it has a different coordinate system, so a comparison would
be false.

The renderer draws **disconnected ordered markers**, not an interpolated
line. Their hue cycles by token order in a braille-like colour sequence;
brightness is the existing projection-fidelity measure, and a large
consecutive-vector change adds a second pixel. That last mark is step size,
not importance. The choice of markers instead of a beam follows the risk
below: a line would overstate continuity in a lossy two-dimensional view.

The raw path stays in process only and is not added to prompts, memory, or
retrieval. A trajectory failure clears the overlay and leaves a normal turn
unaffected.

### 1. Draw the trajectory as a path through the existing projection

The cloud already projects vectors to 2D. Project the current input's token
vectors through **the same** projection and draw them as a connected path —
the beam, in the panel, in the space the memories already occupy.

Why this fits: it reuses `project()` rather than inventing a second
geometry, so a path and a memory point are comparable because they went
through the same transform.

**The honesty requirement is inherited, not optional.** The path runs
through the same lossy projection as the points, so each path node must
carry the same brightness-as-fidelity rule: where the projection
misrepresents a token, that segment renders dim. A confidently drawn line
through a lying projection would be worse than the current panel, not
better, because a line reads as a claim about continuity.

### 2. A second strip: step distance

Keep the entropy strip. Add a parallel strip showing `1 - cos(tokenN,
tokenN+1)`, so the reader can see where the meaning turned as against where
the model was *uncertain*. Those are different questions and it is
interesting when they disagree.

Explicitly not implied: **step distance is not importance.** A large step
means the representation moved, nothing more. The panel's docstring should
say so in the same register it already uses for the arcs it refuses to draw.

### 3. Anchor concept, as text, for the current token

Show the strongest anchor for the token under the cursor. One line, plain.

Required caveat, and it is not a footnote: the phrase comes from
`anchors_v1.json`, a fixed list the operator can read. **The model is not
naming anything.** A weak score means nothing in the dictionary fit, not
that the token was meaningless — and the anchor set is measurably poor at
covering personal memory content, profiling real cached entries at roughly
+0.24 and incoherently.

### 4. The hazard border

Requested three times and still unbuilt. Hazard mode is its case: a mode
that is deliberately slower, holds a second resident model, and runs an
unproven representation should not look identical to ordinary operation.

Constraints from the operator's stated preferences:

- Slow movement. Not strobing.
- Follows the existing dev-mode idiom, which is a **rapid purple-only
  cycle** — the hazard border should be recognisably a different signal, not
  a second interpretation of the same one.
- `tools/pixel_font.py` and the visualizer's corruption idiom are the
  available materials.

## Wiring

The panel stays pure. `assistant/main.py` already owns retrieval
coordination and calls `push_token`; it gains a sibling call — something
like `push_trajectory(path, steps, concept)` — invoked only when
`command_handlers.is_experimental_mode()` and `machinespirit.available()`
are both true.

When machinespirit is unavailable the panel must render **exactly as it does
today**. No empty second strip, no placeholder path. An absent measurement
is absent.

## Risks

- **The path is the most seductive mark on the panel.** A line implies
  continuity and causation more strongly than a point does, and the panel's
  own docstring exists because that temptation was already resisted once
  for arcs. If the fidelity dimming cannot be made to work, draw
  disconnected nodes rather than a line.
- **Two strips halve the vertical space** each gets. Check legibility at
  the smallest terminal the panel currently supports before committing to
  the layout.
- **Cost.** Every rendered frame in hazard mode would need a trajectory,
  which is a second model call. Cache per input rather than per frame.

## Suggested order

1. Hazard border — self-contained, no data dependency, already requested
   repeatedly.
2. Step-distance strip — one new measurement, reuses the existing strip
   renderer.
3. Anchor concept line — text only.
4. Trajectory path — the most valuable and the easiest to make dishonest.
   Do it last, with the fidelity rule working first.
