# QC findings — GitHub presentation and onboarding

Scope: what a stranger sees on GitHub, in the order they see it. The repository
landing page, the release page, and the path from "what is this" to a running
install. Sable's in-application experience is deliberately out of scope and is
tracked separately.

Method: the landing page and release body were read as a first-time visitor
with no prior context. Contrast figures are measured from the actual PNG with
a stdlib decoder, not estimated. Asset references were checked against the
published v0.2.0-beta.6 release rather than against intent.

Reviewed at commit `353913b`, release published 2026-07-28.

---

## 1. The README documents an install path the release no longer uses [HIGH]

`README.md` "Four steps" tells the reader to download `part01` and every
consecutive part by hand, plus the reassembler. That was correct this morning.
The published release now leads with a single downloader that fetches all
twelve files and verifies each one.

The README mentions **none** of the current assets. Counted occurrences:

| Asset | Mentions in README |
| --- | --- |
| `DOWNLOAD_TORMENT_NEXUS_v0.2.0-beta.6.bat` | 0 |
| `INSTALL_ASK_GUARD_PATCH.bat` | 0 |
| `INSTALL_COMMAND_GUARD_PATCH.bat` | 0 |
| docs patch | 0 |
| interface mode | 0 |

Two consequences, and the second is worse than the first. A newcomer follows
the harder path for no reason. And a newcomer who follows the README to the
end finishes **without either guard patch**, having never learned they exist —
which is the exact outcome the reassembler screen, the release notes and the
install guide were all changed to prevent. The README is the one surface that
did not get the message.

**Fix.** Replace "Four steps" with the downloader as the primary path, keep the
manual sequence beneath it as the fallback, and add the guard patches as the
step after `setup.bat`. The wording already exists in
`docs/INSTALL_WINDOWS.md` Step 4 and can be lifted.

---

## 2. The hero image is invisible on GitHub's default theme [HIGH]

`assets/assistant_icon_animated.png`, 256×256, is the first thing on the page.

| Measurement | Value |
| --- | --- |
| Opaque pixels | 11,636 of 65,536 — **17.8%** |
| Mean opaque colour | `rgb(241, 224, 229)` |
| Contrast vs GitHub light `#ffffff` | **1.27:1** |
| Contrast vs GitHub dark `#0d1117` | 14.90:1 |
| WCAG non-text minimum | 3.0:1 |

Light theme is GitHub's default and the majority of traffic. At 1.27:1 the icon
is very nearly white-on-white: a visitor on the default theme sees a blank band
where the project's identity should be, then the title, then a caution block.
The image is not subtle there — it is absent.

This is also the register problem, stated precisely. A pale smiley is a
friendly-software signal. The project is called TORMENT_NEXUS, ships weakened-
refusal models behind a typed acknowledgement, and has a documented corruption
idiom in its own visualizer — torn slabs, dropped cells, overexposed fragments.
The icon is charming and it is doing the opposite of the page's job, which is
to tell someone in one glance what kind of thing they have found.

**Fix.** Two separate changes, and they should not be conflated. For
correctness: give the hero a dark-safe treatment, or ship light/dark variants
via `<picture>` with `prefers-color-scheme`, so it survives both themes. For
register: `tools/glitch_icon.py` already exists and already speaks the
project's visual language. The smiley is a good application icon; it is the
wrong page header. Keeping it in the app and using a corruption-idiom mark on
GitHub resolves both without discarding anything.

---

## 3. The repository description contradicts the README's own warning [HIGH]

Landing-page sidebar, search results, and every shared link carry the
description. The README's caution block does not travel with them.

> Local-first voice AI companion with offline speech, music visualizer,
> guarded self-editing, and optional hardware experiments.

Nothing in that sentence suggests weakened refusal behaviour, an experimental
posture, or a typed acknowledgement gate. Someone who finds the project through
search or a shared link forms their first impression from a sentence that reads
like ordinary consumer software. The README then spends 21 lines correcting an
expectation the description created.

**Fix.** Put the posture in the description. "Experimental" and "abliterated
models" belong in the first fifteen words, not only behind a click.

---

## 4. No custom social preview [MEDIUM]

`usesCustomOpenGraphImage: false`. Every link posted to Discord, Reddit,
Mastodon or anywhere else renders GitHub's generic auto-card: owner avatar,
repo name, description, language bar.

For a systems-art project this is the cheapest available win and currently
unclaimed. The share card is the only image most people will ever see of this
project, and right now it is a template.

**Fix.** A 1280×640 preview using the corruption idiom from finding 2. One
upload in repository settings, no code.

---

## 5. GitHub reports no license, which reads as an oversight [MEDIUM]

`licenseInfo: null`. The sidebar shows nothing, and GitHub's UI treats an
absent licence as an absent decision.

`RIGHTS.md` exists and is deliberate — source-visible, no project-wide reuse
grant yet. That is a considered position and the project is entitled to it. But
GitHub cannot see `RIGHTS.md`, so a developer evaluating the repo sees the same
blank the abandoned repositories show, and the careful reasoning goes unread.

**Fix.** Not a licence change. Link `RIGHTS.md` from the description or add a
`LICENSE` file that states the reservation explicitly, so the absence of a grant
is legible as a choice rather than an omission.

---

## 6. The release page buries the install instructions [MEDIUM]

The published body is 28,805 characters over 534 lines. Order encountered:
model disclosure, experimental-capability table, package contents, *then*
installation.

Everything before the instructions is worth publishing and most of it is
required reading. But a first-time visitor scrolls through roughly a hundred
lines of tables and provenance before learning that one file does the whole
download. The disclosure-first ordering was a deliberate and correct choice
when the alternative was hiding risk behind a download button; it is now also
hiding the easy path behind the risk.

**Fix.** A short orientation block at the very top — three lines: what this is,
what the one file to download is called, and a link down to the disclosure
before you run it. The disclosure stays above the detailed steps.

---

## 7. Topics under-describe the project [LOW]

Current: `local-ai`, `music-visualizer`, `offline-ai`, `piper-tts`, `qwen`,
`raspberry-pi`.

Absent: `llama-cpp`, `windows`, `experimental`, `local-first`, `voice-assistant`,
`abliterated`. Two of those are how people search for exactly this, and
`experimental` is a posture signal that costs nothing.

Also worth noting: `raspberry-pi` is listed, and the Pi is documented throughout
as unbuilt future hardware. A topic is a claim of what the project *is*.

---

## What is already working

Stated plainly, because a findings list reads as though nothing is right.

- **"Choose your path"** is genuinely well built. A task-to-document table is
  the correct shape for a project with this many documents, and it is placed
  before the install instructions rather than after.
- **The requirements table** gives reasons, not just numbers. "About 40 GB free
  during installation — download parts, the reassembled ZIP, and the extracted
  installation temporarily coexist" tells a newcomer *why*, which is what stops
  them guessing.
- **The disclosure is honest and specific.** It names what abliteration does,
  declines to overclaim the Python controls, and says what the project is not.
  Very little software is this straight about its own limits.
- **"Do not use the green Code button"** anticipates the single most likely
  newcomer mistake and heads it off in place. That is real empathy for a
  first-timer.
- **The four-step structure itself** is the right shape. Only its content is
  stale.

---

## Suggested order

1. Finding 1 — the README describes a live release inaccurately, and readers
   who follow it end up without the guard patches.
2. Finding 3 — one sentence, travels everywhere, currently contradicts the
   warning beneath it.
3. Finding 2 — correctness half first (dark-safe rendering), register half
   with finding 4 so one mark serves both.
4. Findings 4 and 6 — presentation polish, no code.
5. Findings 5 and 7 — metadata, minutes each.

Nothing here requires touching the published archive or its checksums. All of
it is repository surface and release-page text.
