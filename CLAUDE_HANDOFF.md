# TORMENT_NEXUS handoff

Updated: 2026-07-27 (America/Toronto). Supersedes the previous Codex handoff,
whose working-tree feature is now commit `1eaa1f4`.

## Start here

```text
C:\Users\evely\Documents\AI_Project
https://github.com/elfdev-tormentnexus/TORMENT_NEXUS
```

```text
branch: master
HEAD:   a6454df
remote: origin/master is at bd74e42 -- FOUR COMMITS BEHIND
```

Nothing in this session has been pushed. The working tree is clean apart from
this file.

```text
a6454df  Let it notice the room                  (system awareness)
0fd8ba2  Give the voice somewhere to fall        (voice delivery)
92b21f7  Double the visualizer to eight scenes   (four new scenes)
1eaa1f4  Play the local library continuously     (Codex's repeat feature)
```

Run the suite before trusting any of it:

```powershell
cd C:\Users\evely\Documents\AI_Project\assistant
python -m unittest tests.test_regressions
```

Expect **308 tests, OK, about 14 seconds**.

## What exists now that did not before

**Local-library repeat** (`1eaa1f4`, written by Codex, verified here). Repeat
is on at launch, follows the filename order `music library` prints, wraps last
to first. `repeat music [on|off]`. A transport lock serialises play, skip, stop
and auto-advance; a generation counter means a manual stop invalidates a
pending transition instead of letting a stale watcher start the next song.

**Eight visualizer scenes** (`92b21f7`). The original four plus `neon horizon`
(perspective wireframe ground, banded sun, spectrum-cut skyline), `plasma flow`
(metaballs), `datastream rain` (glyph columns, beat-driven corruption) and
`wormhole` (projected starfield). Each has its own entry in
`visualizer/reactivity.py`. Adding a scene means three places: that profile
table, `ui._MUSIC_SCENES`, and `ui._make_music_scene()`. Two guard tests exist
because both of the silent failures are easy: a scene listed with no factory
branch, and a scene with no profile (which still runs, on the radial tunnel's
profile, and simply stops responding to what it was built around).

**Voice delivery** (`0fd8ba2`). Tuned against fourteen minutes of reference
dialogue. Within-phrase inflection 0.71 to 2.35 semitones, phrase-to-phrase
pitch 0.18 to 2.21, sentence fall 0.83 to 1.17, 8 kHz spectral share -17 to
-23 dB. Each sentence takes a pitch offset derived from a hash of its own
text, so it varies between sentences and is fixed for any one sentence.
Tunable without editing code:

```text
TORMENT_NEXUS_CADENCE_DEPTH          3.80   inflection depth
TORMENT_NEXUS_CADENCE_FALL           0.60   sentence declination
TORMENT_NEXUS_CADENCE_LIFT           2.20   ceiling on upward steps
TORMENT_NEXUS_PHRASE_PITCH_SPREAD    2.30   between-sentence variation
TORMENT_NEXUS_TILT_DB_OCTAVE         3.4    high-frequency rolloff
TORMENT_NEXUS_PAUSE_SECONDS          0.52   pause after a sentence
```

**Audio-reactive voice face** (`0fd8ba2`). The envelope is taken from the
speech buffer before playback and handed to the UI whole with a timestamp, so
the renderer interpolates at its own frame rate. Smoothing is per second, not
per frame. Constants live at the top of `ui/ui.py` (`SPEECH_ATTACK_RATE`,
`SPEECH_RELEASE_RATE`, `SPEECH_REACH_*`).

**System awareness** (`a6454df`). `core/system_awareness.py` samples the
foreground application and window title, idle time, CPU, memory and power
every 20 seconds, through `ctypes` only. Persists to
`assistant/memory/activity_log.jsonl` as a change log, 14-day retention.
Commands: `activity`, `activity on|off`, `activity forget`. Wired into the
model context beside the clock, and into a two-stage idle wait: a remark
partway into a silence, then the existing "still there?" check.

**Tutorial introduction** (`a6454df`). `core/tutorial.introduction()` — a
written, not generated, self-description that opens the walkthrough.

## What was asked for and does NOT exist

Be direct with the user about these; they have been queued a while.

1. **`sing what you want`** — not started. Not designed beyond a note below.
2. **Come Josephine in My Flying Machine** — not started. This is the oldest
   outstanding request. 1910, public domain (Fred Fisher / Alfred Bryan). The
   user wants **parody lyrics** rewritten as a TORMENT_NEXUS joke, in the
   spirit of the improvised Daisy Bell continuation.
3. **First-run consent for activity awareness** — open decision, see below.
4. **CHANGELOG and docs** for the voice and awareness work — the CHANGELOG's
   Unreleased section covers the scenes but not the voice or awareness.

### The copyright constraint, so it is not relitigated

The user first asked for "You Belong to Me". That is the 1952 Pee Wee King /
Redd Stewart / Chilton Price composition, protected in the US until roughly
2047; their file is a 2014 Courtnee Draper cover. They then proposed keeping
the melody and substituting parody lyrics. That does not clear it: the melody
is the protected part, new words over it make a derivative work, and parody
gets latitude when it comments on the original rather than using it as a
vehicle. They accepted this and chose Come Josephine instead. Daisy Bell is
fine because it is 1892.

### If implementing `sing what you want`

The user's own constraint is the right one: the model may use only the tools
the Daisy Bell engine already has. A 4B model cannot invent a coherent melody.
The design that works is to let it write **lyrics** and select from prepared
rhythmic and melodic phrase templates over a fixed chord progression, with the
system guaranteeing musical validity. Free note generation will produce noise.

## Daisy Bell state

Intro is **52 measures, 65.52s**, vocal enters at 1:05.5, total 148.7s. The
user timed the vocal entry at 1:06 in a YouTube recording. **Unverified
assumption:** if that video has speech before the music, the musical intro is
shorter and this overshoots. One constant:
`offline_voice.DAISY_INTRO_TARGET_SECONDS`. Cache key is
`daisy_bell_machine_v11_`; bump it in `core/config.py` whenever the score,
intro or vocoder changes, or a stale WAV is played instead.

The consonant fix matters if touching the vocoder: a syllable stretched
uniformly to fill a long note smears its consonants, so a held "day" arrives
as "d-d-d-ay". `_sustain_warp` keeps onset and release at spoken pace and
spends the surplus on the vowel. It must not engage for speech rendered at its
own length -- the two frame spans are offset by different amounts, so a naive
comparison quietly reshapes ordinary speech.

## Releasing a beta

Maintainer steps, from `docs/RELEASE_CHECKLIST.md`:

```powershell
.\setup\test_assistant.bat
python tools\package_release.py --archive --skip-download
python tools\package_release.py --verify-only
```

Then record the archive SHA-256, split `dist/TORMENT_NEXUS.zip` into assets
under 2 GiB, and upload the parts with `REASSEMBLE_TORMENT_NEXUS.bat`. Put the
required filenames and the full ZIP checksum in the release notes. Confirm the
release link and filenames in `README.md`, `docs/INSTALL_WINDOWS.md` and
`docs/TROUBLESHOOTING.md`.

Use `--sanitize` if `setup.bat` has been test-run in the tree, because running
it creates the API key and memory files the denylist exists to exclude. Never
test `setup.bat` inside the staged package and then ship that folder.

The published Beta 3 also carries an additive music-visualizer patch built
from `bd74e42`. A **patch 2** must apply cleanly to both an untouched Beta 3
and one that already has `music-visualizer-patch.1`, which means dual accepted
baseline hashes for any file patch 1 already changed, a distinct patch ID and
asset name, and clean-apply plus upgrade tests. The two multi-gigabyte ZIP
parts stay unchanged.

**Ask the user before publishing anything.** They have not authorised a push
or a release in this session.

## Traps that cost time here

- **`core/config.py` has mixed line endings**: 631 CRLF and 10 bare LF. Any
  editor that normalises them turns a one-line change into a 39-line diff.
  Twice the fix was to rebuild the file from `git show HEAD:...` applying only
  the intended edit. `git diff --check` flags every CRLF line in a changed
  region; that is a false positive for this file.
- **Never use PowerShell `Set-Content` on source.** It writes a UTF-8 BOM and
  CRLF, and it double-encoded the deliberate mojibake in
  `DocumentationTests` (`markers = (...)`) via an ANSI round trip. Use the
  Edit tool or Python byte-level writes.
- **`OPENBLAS_NUM_THREADS=1`** for anything touching numpy or librosa audio,
  or it hangs forever rather than erroring.
- Long uptime fills the 65 GB commit limit until 2 MB allocations fail; it
  looks like a corrupt model and is not. Reboot.
- No `ffmpeg` on this machine, and `developer.valvesoftware.com` sits behind a
  bot wall that must not be worked around. Ask the user to paste content or
  export audio locally.

## Verification habits worth keeping

The user values honesty over agreeableness and expects fixes to be *verified*,
not described. Two failures here are worth remembering:

- A guard test that passes with the bug re-injected is worthless. Two written
  this session did exactly that and had to be strengthened. Inject the
  regression and confirm the test fails.
- A measurement can lie. A "last 20% of the phrase" metric reported a rise on
  a phrase whose contour ended 4.1 semitones down. Check the instrument
  before trusting a surprising result.

## Privacy and safety boundaries

Never commit, package, or quote in a bug report:

- `assistant/music/*` (someone else's copyright)
- `assistant/memory/activity_log.jsonl` (window titles: file names, URLs,
  message previews)
- conversation history, extracted memories, runtime logs
- API keys, passcodes, pairing PINs, tokens
- generated shortcuts containing absolute local paths

`DENY_PATTERNS` in `tools/package_release.py` and `.gitignore` are kept in
step. Preserve both.

`edit_guard` denies `main.py`, `command_handlers.py`, `core/config.py`,
`core/dev_auth.py`, `ui/ui.py`, `core/persona.py`, `editing/` and `tests/`.
The persona and the suite are on that list for the same reason as the rest: an
editor that can rewrite its own honesty rules, or the tests that judge it,
makes both a formality. **Do not widen this without asking.**

The repository still has no project-wide licence. Do not describe it as
freely redistributable beyond the licences of bundled third-party components.

## Open decisions for the user

1. **Push?** Four commits are unpushed.
2. **First-run consent.** Activity awareness currently defaults on, with full
   window titles, and may comment unprompted. That is what the user chose for
   their own machine. It also means a beta tester who installs the release
   gets their document names and URLs sampled without being asked. The
   suggestion on the table is to keep their install as-is and have a *fresh*
   install ask once. Undecided.
3. **Daisy intro length.** 66 seconds of instrumental before any singing is
   faithful to the reference but a long wait for a command-triggered easter
   egg.

## On the model editing this project

The user asked directly whether TORMENT_NEXUS can be trusted to code on its
own the way an external assistant does. The honest answer given was no, and
it should not be quietly walked back: Qwen3-4B cannot hold a subsystem in
mind, and the abliteration erodes the instinct to say "I do not know" or "I
should not change that" -- the reflex most wanted in something editing its own
source. The 308-test suite is what makes any autonomy tolerable, because
anything that breaks a test is rejected without a human. Keep the guardrails.
