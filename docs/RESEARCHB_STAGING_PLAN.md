# researchB — staged verification plan

beta-5 to researchA was one enormous jump. Everything moved at once, so when
something looked wrong there was no way to tell which change caused it, and the
only way to find out was to hold the whole thing in your head at the same time.

This plan exists so researchB is not that. It is cut into stages that each end
at a **stopping point**: a place where the tree is coherent, the tests pass,
the result is written down, and walking away costs nothing. Nothing later
depends on doing two stages in one sitting.

Each stage says what changed, what to measure, and roughly how long the
measuring takes. The time estimates are for the *machine*, not for you.

---

## How to use this

Work one stage. Record its numbers in the table at the bottom. Stop.

If a stage fails, that is information, not a setback — the point of cutting it
this way is that a failure names its own cause. The stage that failed is the
change that broke it.

**Do not run stages 2 through 5 on the same day.** The whole reason this
document is staged is that the last release was not.

---

## Stage 0 — the baseline, before anything else

Everything after this is a comparison, so this is the only stage that must
happen first. It changes nothing.

| check | how | expect |
| --- | --- | --- |
| Full suite | `.\setup\test_assistant.bat` | no failures, 2 skips (the total grows; see the record below for the count on the day) |
| Calibration | `calibrate` in hazard mode | drift `0.000000` on all seven rows |
| Anchor digest | printed by `calibrate` | unchanged from researchA |
| Model identity | `machinespirit status` | `bge-small-en-v1.5-q8_0`, pooling `mean` |

**~10 minutes.** Write the numbers down even though nothing has changed. A
baseline you did not record is not a baseline.

**Stop here.**

---

## Stage 1 — what has already landed

These are committed and unpushed. They are verified by the suite, but the suite
does not press the buttons a person presses.

### Automated

Covered by the full suite. No new work.

### By hand

| # | check | expect |
| --- | --- | --- |
| 1.1 | `super dev mode`, enrol an alphanumeric key at the masked prompt | accepted; nothing echoed to the screen |
| 1.2 | Re-enter with wrong case | refused |
| 1.3 | `super dev mode 1611KJV` inline | refused, tells you to use the prompt |
| 1.4 | `yolo mode` before unlocking | refused, names the unlock as the fix |
| 1.5 | `yolo mode` with a short window (`TORMENT_NEXUS_SUPER_DEV_SESSION_SECONDS=300`) | stops on its own; report names the reason |
| 1.6 | `enable all features` in ordinary mode | activity and audio start; each line names its off-switch |
| 1.7 | `activity off`, `exit audio` | both actually stop |
| 1.8 | Repo root on GitHub | governance docs and launchers only |

**~30 minutes**, most of it 1.5 waiting.

**Stop here.** This is a coherent release on its own if you want one.

---

## Stage 2 — the vector panel

*Built. machinespirit above, machinesoul below. 2.1 has been run once
against the live servers and passed; the rest are still to do by hand.*

The panel becomes machinespirit on top, machinesoul below. Both halves change
source, so both need checking against something that is not the panel.

| # | check | expect |
| --- | --- | --- |
| 2.1 | `trace` a known anchor phrase, compare panel to text readout | same concept, same token |
| 2.2 | Panel at 150x32 exactly | nothing clipped |
| 2.3 | Resize across the threshold repeatedly | no tearing, no stale columns |
| 2.4 | Resize mid-page with a long reply open | pager stays coherent |
| 2.5 | A turn that retrieves nothing (a greeting) | no false activity |
| 2.6 | machinesoul half against a real capsule | the field matches what `machinesoul.py` writes |

2.1 and 2.6 are the ones that matter: a panel that renders beautifully and
disagrees with the instrument it claims to show is worse than no panel.

**~45 minutes.** **Stop here.**

---

## Stage 3 — the council

Six embedding models, all SHA-256 verified against
`models/embedding/INTERLINGUA_MODEL_REGISTRY.json`. None of them changes
ordinary retrieval, which is the property to actually confirm.

| # | check | expect |
| --- | --- | --- |
| 3.1 | Re-verify all six digests | 6/6, unchanged |
| 3.2 | Load each in turn, embed one fixed phrase | all six answer; none crashes |
| 3.3 | Ordinary retrieval with the council present | identical to stage 0 |
| 3.4 | Peak RAM with two servers up | fits, with the 14B's needs in mind |
| 3.5 | Quarantined partial | still quarantined, still unregistered |

3.3 is the whole point. The council is an observatory, not a committee — if
adding it moves ordinary retrieval, something is wired in that should not be.

**~40 minutes.** **Stop here.**

---

## Stage 4 — benchmarks worth repeating

The gap this fills: researchA's numbers were measured once, at the end, when
nothing could be done about them. These are cheap enough to re-run at every
stage above, and that is the intent.

| benchmark | source | researchA figure |
| --- | --- | --- |
| Calibration drift | `calibrate` | `0.000000`, seven rows |
| Anchor reconstruction | `tools/machinespirit_codec.py` | 0.9243 mean cosine, 100% self-retrieval |
| Transpose decoder control | same | 0.6635, 6% |
| Rosetta agreement | `tools/rosetta_whitening_probe.py` | 0.444 raw, 0.471 anchor-centred, ceiling 0.579 |
| Held-out pairwise cosine | `tools/whitening_probe.py` | +0.5462 raw |
| Suite | `.\setup\test_assistant.bat` | no failures / 2 skips |

Any of these moving without a change that explains it is the signal to stop and
look, not to keep going.

**~20 minutes for the set.**

---

## Stage 5 — the cut

Only after 1 through 4 are green and recorded. Follow
[the existing method](MACHINESOUL_RELEASE_CUT_METHOD.md) and
[release checklist](RELEASE_CHECKLIST.md); nothing here replaces them.

| # | check | expect |
| --- | --- | --- |
| 5.1 | Suite immediately before cutting | green |
| 5.2 | Asset set in `README.md` and `docs/INSTALL_WINDOWS.md` | identical sets |
| 5.3 | Decompile every capsule on a clean directory | every SHA-256 matches |
| 5.4 | Install from the decompiled tree | reaches `I UNDERSTAND` |
| 5.5 | First launch from that install | defaults off as documented |
| 5.6 | Tag, then verify it dereferences where you meant | correct commit |

**5.3 and 5.4 are the release.** Everything else is preparation. Budget a
session for these two alone and do not append them to stage 4.

---

## Record

| stage | date | result | notes |
| --- | --- | --- | --- |
| 0 baseline | 2026-07-30 | pass | Suite 1007 pass / 2 skips at the rename; 1021 / 2 skips after the receipt work landed later the same day. Calibration 7/7 rows, drift `0.000000`. Anchor digest `b5421687…1690fd`, 184 anchors (122 core + 16 project + 46 life), dictionary v2. |
| 1 landed changes | | | |
| 2 vector panel | 2026-07-30 | 2.1 only | `trace` on the README's own example: panel and text readout agreed on the same concept at the same token. 2.2–2.6 not run. |
| 3 council | | | |
| 4 benchmarks | | | |
| 5 cut | | | |

An empty row is a stage not run. That is a fine state to leave this in.

### How the stage 0 and 2.1 rows above were established

Recorded after the fact, so the means matters as much as the result.

- Suite count, anchor digest, anchor counts and dictionary version were
  re-measured on 2026-07-30 while writing this row — the suite by running it,
  the anchors by reading `machinespirit.dictionary()`, which loads the anchor
  file directly and needs no server. The digest matched the figure carried
  forward from earlier the same day.
- Calibration drift, `machinespirit status` model identity, and the whole of
  2.1 were run live earlier on 2026-07-30, against the same tree, and are
  transcribed here rather than re-measured. Stage 2.1 in particular needs the
  live servers and a rendered panel.

Stage 0's suite figure was taken with the researchA to researchB rename
applied (`RELEASE_VERSION`, the four version pins). The baseline is therefore
the renamed tree, which is the thing later stages should be compared against.
