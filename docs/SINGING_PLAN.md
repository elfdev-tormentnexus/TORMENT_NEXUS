# Plan: Come Josephine, and `sing what you want`

Written for the next maintainer session. Two features, in this order — the
first builds the machinery the second needs.

> **Continuation status (2026-07-28):** the Part 1 `Song` dataclass and
> generic build/mix/sing wrappers now exist in the current working tree. This
> document remains the design and safety contract for that refactor, but it
> does **not** mean Come Josephine is playable: its public-domain score
> transcription, original lyrics, command/session plumbing, and listening
> validation are still open. `sing what you want` is also still unimplemented.

## Hard constraint, decided already

Only public-domain melodies may be encoded in this repository. Daisy Bell
(1892) is fine. "You Belong to Me" is the 1952 King/Stewart/Price
composition and is **not** usable, and substituting parody lyrics does not
help, because the melody is the protected part and new words over it make a
derivative work. This was discussed with the user and settled; do not reopen
it.

"Come Josephine in My Flying Machine" (1910, Fred Fisher / Alfred Bryan) is
public domain and was chosen instead.

**Transcribe the melody from an actual public-domain score** (Library of
Congress or IMSLP both hold the 1910 sheet music). Do not reconstruct it from
memory — a wrong transcription is both bad music and a bad look for a
repository that makes a point of its licensing.

---

## Part 1 — Generalise the singing engine

Everything today is Daisy-specific and lives in
`assistant/voice/offline_voice.py`. Do **not** copy-paste it for a second
song. Extract first, then add.

### What a song currently is

```python
# (syllable, midi_note, duration_in_eighth_notes); None note = rest
DAISY_CHORUS = (("day", 62, 6), ("zee", 59, 6), ...)
DAISY_EIGHTH_SECONDS = 0.21          # tempo
DAISY_HARMONY = {"G": (43, 55, 59, 62), ...}   # chord -> midi voicing
DAISY_CHORD_PROGRESSION = ("G", "G", "G", "G7", ...)   # one per measure
DAISY_INTRO_MELODY = ((62, 6), (59, 6), ...)   # (note, duration), no words
```

One measure is **6 eighths**. The chord list must cover
`ceil(total_eighths / 6)` measures or the accompaniment stops partway.

### Suggested shape

A `Song` dataclass (or plain namedtuple) holding: `name`, `score`,
`eighth_seconds`, `harmony`, `progression`, `intro_melody`,
`intro_target_seconds`, `cache_key`. Then:

- `_build_song_audio(song, cancelled, phase_changed)` — from
  `_build_daisy_audio`
- `_song_accompaniment(song, np, sample_rate, output_samples)` — from
  `_daisy_computer_accompaniment`
- `_mix_song(song, np, vocal, sample_rate)` — from
  `_mix_daisy_performance`
- `sing(song, cancelled, phase_changed)` — from `sing_daisy_bell`

Keep `sing_daisy_bell` as a thin wrapper so nothing downstream breaks.

### Things that will bite

- **Cache keys are per song and must be versioned.** `VOICE_DAISY_CACHE` in
  `core/config.py` carries `daisy_bell_machine_v11_`. Give each song its own
  file and bump its version whenever its score, intro, tempo or the vocoder
  changes, or a stale WAV plays instead of your edit.
- `_sustain_warp` already keeps consonants intact on long notes. Leave it
  alone; it engages automatically for any stretch over 1.25x.
- Syllables are synthesised **individually** by Piper and cached per unique
  string, so phonetic spellings matter: "an sir" for "answer", "ma sheen"
  for "machine". Isolated syllables that read wrong will sing wrong.
- The vocal score and the chord progression are aligned by measure. An intro
  of a non-whole number of measures slides the whole song off the grid.

### Plumbing per song

1. `voice/session.py` — request/consume flags, mirroring
   `request_daisy_bell` / `consume_daisy_bell_request`.
2. `main.py` — a loop mirroring the `sing daisy bell` branch, which sets
   `ui.set_voice_speaking(...)` on the singing phase.
3. `commands/command_handlers.py` — a `@command(..., dev_only=False,
   group="session")` handler mirroring `handle_sing_daisy_bell`.
4. `core/tutorial.py` and README/CHANGELOG.

---

## Part 2 — Come Josephine

Melody and chords transcribed from the 1910 score. **Lyrics are original**:
the user wants a TORMENT_NEXUS parody, the same joke as the improvised second
verse of Daisy Bell (`DAISY_QWEN_CONTINUATION`). The original song is a woman
being carried into the sky by a machine, which writes itself.

Keep the parody's syllable count and stress matched to the melody, exactly as
the Daisy continuation reuses the chorus's own notes and durations. Write it
to be sung, then check it by singing it.

Suggested command: `sing come josephine`.

An instrumental introduction is optional here. Daisy Bell has one because the
1961 IBM recording does; this song has no such reference, so a short lead-in
(4–8 measures) is enough.

---

## Part 3 — `sing what you want`

Let the model improvise a song, with **only the tools the Daisy Bell engine
already has**: the same oscillator accompaniment, the same vocoded voice, the
same note/duration score format.

### The design constraint that makes this work

Qwen3-4B **cannot invent a coherent melody**. Asking it for free note tables
will produce noise. What it can do well is write lyrics.

So: the model writes **words**, and chooses from **prepared musical
material**. The system guarantees musical validity.

Concretely:

1. Ship a small library of phrase templates — rhythm patterns paired with
   melodic contours that fit a fixed chord progression, in the same
   turn-of-the-century idiom as Daisy Bell. Four to eight is plenty.
2. Ask the model for: a title, a mood, and lyrics as **lines with a target
   syllable count per line**, that count dictated by the chosen templates.
3. Fit syllables to the template's notes mechanically. Where a line is short,
   hold a vowel; where long, split a note. Never let the model choose pitches.
4. Validate before rendering: every syllable has a note, every measure has a
   chord, total eighths divide into measures, no note outside a sane range
   (MIDI 45–75), lyrics are non-empty and contain no stage directions.
5. Fall back to a fixed template-only instrumental if validation fails. It
   must never crash the voice.

### Guardrails

- Same rule as everywhere else: the model's output is **data, not
  instructions**. Strip anything that looks like a command or a prompt.
- Cache by a hash of the generated score, so repeating a song is instant and
  a good one can be kept.
- Cap total length (Daisy Bell is 148s; 90s is plenty here) so a runaway
  generation cannot produce a twenty-minute song.
- The generation step needs a `cancelled()` check like every other long
  operation, or Escape will not interrupt it.

---

## Verification, for both

`python -m unittest tests.test_regressions` from `assistant/`. The suite count
evolves; use the completed run in the current handoff rather than this plan as
the source of truth.

Add tests that mirror the existing Daisy ones:

- score length, note range, rests present
- chord progression covers every measure
- intro, if any, is a whole number of measures
- phonetic spellings survive (the Daisy tests assert on specific joined
  syllable strings)
- for freestyle: a malformed or hostile model response is rejected and falls
  back rather than raising

Two habits worth keeping from the last session:

- **A guard test that passes with the bug re-injected is worthless.** Inject
  the regression and confirm the test actually fails. Two tests written last
  session did not, and had to be strengthened.
- **Check the instrument before trusting a surprising measurement.** A "last
  20% of the phrase" metric reported a pitch rise on a phrase whose contour
  ended 4.1 semitones down.

Do not run `Set-Content` over source files: it writes a UTF-8 BOM and CRLF
and has already corrupted deliberate mojibake in the test suite. Pin
`OPENBLAS_NUM_THREADS=1` for anything touching numpy audio.
