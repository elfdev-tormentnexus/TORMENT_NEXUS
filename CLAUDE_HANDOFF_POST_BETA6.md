# Handoff — Beta 6 published, 2026-07-28

Written at the operator's request as usage ran short. Supersedes
`CLAUDE_BETA6_HANDOFF.md` on every point where they disagree: that note was
accurate when written and every blocker in it is now cleared.

## State

```text
branch:   beta-6-release   pushed through efdeee2
release:  v0.2.0-beta.6    PUBLISHED as prerelease, 21 assets
tag:      v0.2.0-beta.6 -> 353913b
tests:    644 pass, 2 expected symlink skips, ~26-32s
disk:     ~17 GiB free on C:
name:     Sable, set operator-chosen, gitignored
```

The release is **live**. https://github.com/elfdev-tormentnexus/TORMENT_NEXUS/releases/tag/v0.2.0-beta.6

All 21 assets were digest-verified against local files by streaming each one
back down and hashing it — not size-checked, hashed. Zero mismatches.

## The thing that cost two previous sessions

**AVG's HTTPS scanning silently stalls large uploads to exactly zero bytes
per second while small requests succeed normally.**

Three `gh release upload` workers sat on 2 GB assets for 79 minutes moving
nothing, while `gh api` returned in 1.8s and every sub-4 KB asset uploaded
in about 3 seconds. Nothing errored. Both prior sessions read the stall as a
broken uploader and rebuilt the uploader. The uploader was fine both times.

Throughput went 0 → 23 MiB/s the moment the operator disabled Web Shield,
with nothing else changed. It was disabled machine-wide on 2026-07-26 per an
earlier memory and had re-enabled itself by 2026-07-28 — **assume it is back
on and re-check rather than trusting it stayed off.**

Diagnosis recipe, before touching any code: sample
`(Get-NetAdapterStatistics | Measure-Object SentBytes -Sum).Sum` 20–30s
apart. A literal zero delta with a live Established connection is the AV
path. Also check for orphaned workers from prior sessions with
`Get-CimInstance Win32_Process` — retry loops respawn children, and two
uploaders racing the same asset with `--clobber` produce HTTP 404s that look
like an entirely separate bug.

Codex's uploader at `C:\Users\evely\TN_UPLOAD\upload_assets.ps1` is **well
built** — detached, disjoint groups A/B/C/D, retry with backoff, skips
assets already present at matching size. Do not rewrite it. It completed all
uploads once the network path was fixed.

## Shipped this session

Seven commits on `beta-6-release`, all pushed:

| Commit | What |
| --- | --- |
| `10c1b73` | `/ask` history-reference guard, fails closed in Python |
| `256ce20` | that guard as a hand-applied patch asset + builder |
| `08dff77` | reassembler names the patches it deliberately will not apply |
| `ab7a724` | install guide gains the manual patch step; docs patch carries it |
| `930fe06` | near-miss command gaps the first fix could not reach |
| `92a75b4` | `*.local.bat` ignored so personal launchers cannot ship |
| `353913b` | one-double-click bulk downloader |
| `efdeee2` | GitHub presentation QC audit |

### Two guard patches, both hand-applied

They replace **manifest-hashed files**, unlike the documentation patch, so
applying them makes an installed tree diverge from the published archive
checksum on purpose. That is why the reassembler names them and refuses to
run them. Both were verified against a real extracted tree: clean apply with
backup, "already applied" on rerun, non-zero exit and no change on a tree
whose file had been edited, and both applied to one tree without disturbing
each other.

- `INSTALL_ASK_GUARD_PATCH.bat` → `assistant/main.py`
- `INSTALL_COMMAND_GUARD_PATCH.bat` → `assistant/commands/command_handlers.py`

### The near-miss finding, because it recurs

`near_miss_command`'s own docstring claimed `drop all` and `finish` were
handled. They were not. The shape it matched is a real command name plus one
stray word, and **no command contains the word "drop"**, so `drop all` was
never one word away from anything. A bare single word cannot match a rule
needing one more word than the command name has. `finish goal` missed
because comparison was exact per word.

Live evidence: `drop all` → "I'm dropping everything." Nothing ran.

Now: one typo tolerated per word (excluding words under three characters),
plus a state-changing-verb rule for phrases resembling no command at all.
Any conversational word in the phrase disqualifies it, which keeps "can you
drop me a line" as chat.

## Uncommitted — the entire creative thread

Nothing below is committed. All working-tree only.

```text
tools/vector_pixel_compiler.py    byte -> pixel codec, round-trip verified
tools/vector_pixel_codec.py       vector coords -> pixel, with measurement
tools/pixel_font.py               5x7 A-Z 0-9 bitmap font, reusable
tools/build_easter_egg.py         3-layer image, self-decoding
tools/build_logo_mark.py          the cryptic mark, SCAN ME
tools/generate_logo.py            SABLE-from-projection (UNRESOLVED, see below)
docs/THE_STORY_OF_SABLE.md        919 words, the payload
assets/sable_mark.png             the mark
assets/sable_easter_egg.png       explicit version
assets/sable_semantic_space.png   43 real bge-small vectors as pixels
assets/sable_story.png            story as pure data
assets/logo_sable*.png            unresolved wordmark attempts
assets/social_preview.png         unresolved
```

### What was measured, and what it means

**Byte → pixel is pure overhead.** 5,385-byte story: zlib alone 2,566 bytes,
pixel-compiled PNG 3,384. The pixel layer costs +32% for zero functional
gain. Its only real value is transport through channels that carry images
but not files.

**Vector → pixel is a different question with a different answer.** On 43
real `bge-small` vectors:

| | Bytes | vs raw |
| --- | --- | --- |
| float32 raw | 66,048 | — |
| float32 + zlib | 61,541 | 93.2% |
| uint8 quantised | 16,512 | 25.0% |
| quantised PNG | 17,152 | 26.0% |

Cosine after round trip: mean 0.999929, worst 0.999921.

**The win is quantisation — exactly 4.00× — not the pixels.** PNG costs
+3.9% over raw quantised bytes. But note zlib barely touches float32 (93.2%)
because mantissas are high-entropy, so "just compress it" fails here in a
way it did not for bytes. Pixels are the *container*, not the compression,
and that framing must survive into any write-up.

**Actionable spinoff, unbuilt:** `assistant/cache/embeddings.json` is 906 KB
holding **67 vectors** as JSON floats. Quantising to uint8 with a stored
scale is a genuine order-of-magnitude win at ~7e-05 cosine error, with no
visual component. This is the real optimisation the art question produced.

**Product quantisation was being probed when usage ran out.** The operator's
"vectors describing vectors" intuition maps exactly onto PQ, which is
established (FAISS), not unexplored. The economics decide it:

```text
codebook   = K * D * 4 bytes   (fixed, independent of M)
per vector = M bytes           (at K <= 256)
```

At K=256, D=384 the codebook alone is 393,216 bytes. **The corpus is 110
vectors.** PQ almost certainly loses badly at this scale and only pays above
roughly a thousand vectors. `scratchpad/pq_probe.py` is written and ready to
run and will produce the crossover table — **it was never executed.** Do not
report its numbers without running it.

## Open queue, in the operator's stated order

1. **Converter as a real utility** — a `data to pixel` command in Sable
   rather than three loose scripts. Explicitly requested, "like youtube to
   mp3".
2. **Write up the measured findings** in `docs/`, negative attribution
   included, the way the Wi-Fi sensing result was published.
3. **Embeddings-cache quantisation** — the actual performance win.
4. **Hazard border** — a slowly moving border around the UI signalling that
   a hazardous mode is active. Requested twice; `tools/pixel_font.py` and
   the visualizer's corruption idiom are the materials.
5. **Theoretical concept** the operator wanted to explore jointly; never
   started.

The operator also said **future updates should be confined to the next beta**
after the two guard patches. The easter egg, mark and hazard border are new
features rather than fixes, so they likely belong in beta 7, not a third
patch on a published release. This was raised and not resolved.

## GitHub presentation — audited, not fixed

`docs/QC_FINDINGS_GITHUB_PRESENTATION.md` has seven findings. The two that
matter:

- **The README still documents the manual part-by-part download** and
  mentions none of the current assets — not the downloader, not either guard
  patch. Anyone following it finishes **without the guard patches** and never
  learns they exist. Highest priority.
- **The hero icon measures 1.27:1 against GitHub's default light theme**
  where the non-text minimum is 3.0:1, with 17.8% of pixels opaque. It is
  effectively invisible for most visitors.

The operator has since decided: **the pixel/vector mark becomes the project
logo, the smiley stays solely as the launcher and shortcut icon.**
`assets/sable_mark.png` is the candidate and is not yet wired into the README
or the social preview.

Also unfixed: repository description does not mention the experimental
posture, no custom social preview, GitHub reports no licence.

## Gotchas earned this session

- **`gh` is not on PATH.** `C:\Program Files\GitHub CLI\gh.exe`.
- **A checksum cycle exists and has a required order.** The downloader hashes
  the docs patch, that patch carries the release notes, and the notes state
  the downloader's hash. Finalise notes → rebuild patch → record its digest →
  rebuild downloader → record its digest → **stop**. Rebuilding the patch
  again invalidates the downloader that just pinned it.
- **Never hand-edit a generated artifact.** The reassembler comes from a
  template in `package_release.py`. Regenerating it unmodified first proved
  the generator reproduces the published file byte-for-byte, so the only
  delta was the intended change.
- **Batch: avoid `if exist` nested inside parenthesised blocks.** Use flat
  `goto` labels. Both reassembler branches were executed, not read.
- **The downloader's reassembler prompt defaults to yes.** Piped input landed
  on the wrong prompt twice during testing and joined an 11.5 GB archive,
  filling the disk to 0.00 GiB free both times. Recoverable, but test in a
  directory with headroom and verify free space after.
- **Hardlinks (`mklink /H`) let you stage a full 11.5 GB asset set for
  testing at zero disk cost.** Deleting a link does not touch `dist/`.
- **PCA follows variance.** The logo failed twice because off-plane noise at
  σ=0.62 across 48 dims swamped the planted signal, so `project()` recovered
  the noise. This is written up in `generate_logo.py`.
- **`generate_logo.py` is unresolved.** `project()` recovers the subspace but
  not the planted axes, then normalises each axis independently, so the
  letterforms come out sheared. The mark supersedes it; consider deleting.
- **Contrast has a solvable band, not a taste.** Clearing 3:1 on both white
  and `#0d1117` means luminance in [0.132, 0.300]. Guessing HSV values does
  not reach it.
- **The pixel payload survives file copies, not re-encodings.** A screenshot
  or a transcoding platform destroys it silently while the image still looks
  identical.

## Verification standard this project holds to

Fixes are applied and individually verified, never described. A guard test
that passes with the bug re-injected is worthless — every guard added this
session was confirmed by restoring the defect and watching the test fail
with the original symptom, then reverting. Stage explicit paths, never
`git add -A`. Use `git commit -F`; PowerShell mangles heredocs.
`OPENBLAS_NUM_THREADS=1` for anything touching numpy or librosa.
