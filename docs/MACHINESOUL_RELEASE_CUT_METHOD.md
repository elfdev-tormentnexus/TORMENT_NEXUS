# How researchA is cut into machinesoul fields

This document records why researchA is divided where it is, how the cutter
chooses a seam, what the review map proves, and what the heuristic does **not**
prove. The implementation is `tools/machinesoul_release.py`; the exact seams
for one release live in its hashed JSON plan, Markdown table, and animated PNG
cut map.

## Why the install tree is cut directly

researchA is not first flattened into ZIP, tar, or another public archive.
Doing so would erase the boundaries the operator wanted machinesoul to
respect: complete files, the ends of Python modules, and quiet structural
space between rules, classes, and functions.

The verified staged directory is the source. The planner inventories every
regular file in stable path order and records its length and SHA-256. Links and
Windows reparse points are refused so a build cannot silently pull data from
outside the staged tree. The reassembler later recreates that directory file
by file.

This direct design also makes the public claim simpler: every downloadable
payload is a machinesoul PNG/APNG vector field. There is no hidden conventional
archive layer whose boundaries happen to be painted as an image.

## The size boundary

GitHub release assets have a 2 GiB ceiling. researchA uses a lower maximum
preserved extent of `1,797,000,000` source units per capsule, leaving margin
for the machinesoul header, PNG/APNG structure, and variation in compression.

machinesoul maps ordered four-coordinate integer vectors to RGBA pixels, so an
in-file seam is aligned to four coordinates. A boundary never divides a
complete RGBA vector.

The ceiling answers “how late may this capsule end?” It does not decide where
the cut should be. The planner searches backward for a better seam.

## Seam priority

The planner applies these rules in order:

1. **Complete-file boundary.** If the next whole file does not fit, finish the
   capsule after the previous file. This is preferred even when it leaves a
   small capsule. Structure is more important than packing every asset to the
   ceiling.
2. **Text structural boundary.** If a single text file itself exceeds the
   capsule, search the final 32 MiB before the ceiling for a blank seam before
   `def`, `async def`, `class`, `if __name__`, or a rule separator. This is the
   concrete version of the operator's request to prefer Python EOF and the
   quiet space between rules and functions.
3. **Quiet vector window.** If the oversized file is binary, or no structural
   text seam exists, score aligned windows in the final 32 MiB and choose the
   lowest-activity candidate.
4. **Forced fallback.** Only when there is no meaningful search span may the
   planner use the aligned ceiling directly. The APNG marks this separately in
   orange so it cannot masquerade as an intentional quiet seam.

The end of a complete file and the end of the release are treated as
zero-activity structural seams.

## What “quiet” means in the cutter

For an oversized field, the planner samples 64 KiB windows at 128 KiB steps
through the last 32 MiB before the size ceiling. It also scores the ceiling
itself. Lower activity wins; an equal score chooses the later boundary.

The activity score combines three normalized observations:

```text
activity = 0.55 × fast-compression ratio
         + 0.35 × motion between sampled RGBA vectors
         + 0.10 × coordinate energy
```

- **Compression ratio** rewards locally repetitive or regular regions.
- **Vector motion** rewards regions whose neighbouring sampled RGBA vectors
  change less.
- **Energy** is a small preference for lower coordinate intensity rather than
  the main decision.

This is a deterministic local heuristic, not a learned model. Its constants,
search radius, window, and stride are stored in the versioned source. The JSON
plan records every candidate offset and activity so the selected line can be
audited rather than trusted as an unexplained result.

## Why use the emptiest available space

All exact aligned cuts are reconstructable. Choosing a low-activity seam does
not create stronger cryptographic integrity than a noisy seam; the digest
chain provides that guarantee. The reason is structural and visual:

- keep human-authored source units whole whenever possible;
- avoid cutting through an active rule, class, or function body;
- when a model must be divided, place the visual interruption in the flattest
  nearby portion of the ordered field; and
- make the cut describe the data-preservation language rather than only a
  storage limit.

The quietness hypothesis is therefore used to choose among already safe
aligned candidates. It is not presented as evidence that the model contains a
semantic void there, and it is not allowed to replace the hashes.

## The review-bound APNG

Planning writes no capsule. It produces:

- a JSON plan containing the complete file inventory, segment map, candidate
  activity profiles, and proposed capsule names;
- a Markdown table naming every seam, offset, extent, and activity; and
- a lossless APNG whose first frame shows the whole release and whose later
  frames show one proposed capsule and local activity graph each.

The visible colors are:

| Color | Meaning |
| --- | --- |
| green | end of a complete file or release |
| cyan | blank text seam before a rule, function, class, or main guard |
| magenta | selected quiet aligned in-file vector window |
| orange | forced fallback |

The APNG embeds the SHA-256 of the exact JSON plan it renders. The cutter
requires that same digest as `--approved-sha256`; a changed source file or a
changed plan is refused. This binds human review to the map actually cut.

## What a capsule contains

Each capsule decompiles to one internal `.msv` vector segment. Its manifest
entries name:

- the relative source path;
- the source offset and segment length;
- the segment's offset inside the decoded field; and
- the SHA-256 of that exact source range.

Small alignment gaps between adjacent entries are zero-filled. That is why
the sum of capsule `data_size` values can exceed the sum of file sizes by a
few hundred units. The padding is declared layout, not duplicated source.

The local absolute staging path exists only in the private review plan so the
cutter can revalidate its source. It is removed from the public manifest.

The main Windows tree and optional 14B model are planned and cut separately
because one is a directory while the other is a companion file. Their two
verified manifests are then placed in one `SABLERESEARCHA_MANIFEST1` JSON
record before that record is itself encoded as machinesoul. The reassembler
requires the caller to select `windows` or `optional_14b`; it cannot silently
confuse the companion model with the main installation.

## Verification while cutting

For every approved capsule, the cutter:

1. reads only the planned source ranges and writes the temporary `.msv`;
2. builds the PNG/APNG through streaming machinesoul;
3. refuses a capsule that approaches GitHub's asset ceiling;
4. immediately decompiles the finished capsule through the streaming inverse;
5. compares the decoded digest with the source segment; and
6. deletes temporary material, keeping no capsule that failed its own inverse.

Peak memory remains bounded because neither the builder nor extractor loads a
multi-gigabyte field at once.

## Verification while reassembling

The recovered reassembler treats the public manifest as hostile input. It
refuses unsafe or duplicate paths, missing or damaged decoded segments, range
hash failures, gaps, overlaps, unexpected offsets, and final files whose size
or digest differs from the staged source.

It builds into a temporary sibling directory and replaces the requested
target only after every file passes. A failed reassembly therefore does not
present a partial installation as complete.

## The researchA policy produced by this method

The main Windows cut should show source and documentation files remaining
whole, with unavoidable in-file seams confined to the bundled GGUF models.
The optional 14B companion is one GGUF, so its non-final seams are quiet
aligned model windows and its last seam is the end of the model.

The exact capsule counts, offsets, activity scores, plan fingerprints, and
APNG fingerprints are release records, not constants in this document. They
must be regenerated whenever the staged source changes. An old map can explain
history; it cannot authorize a new cut.
