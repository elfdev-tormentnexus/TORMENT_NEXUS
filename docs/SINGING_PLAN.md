# Implementation record: Come Josephine and `sing what you want`

Implementation status (2026-07-31): both features are implemented and pass
their focused automated tests. The generic `Song` path dispatches Daisy Bell
and Come Josephine. `sing come josephine` performs the public-domain 1910
chorus plus an original answering verse. `sing what you want [about
<subject>]` lets the local director choose between two fixed trusted tunes and
supply only validated one-syllable lyric tokens.

This began as a design plan and is now an implementation record. The current
source and tests are authoritative where an older handoff differs. Automated
validation is complete; physical listening and the Windows sleep/lock/device
recovery matrix still require a person at the machine.

## Rights and score source

Only public-domain melodies are encoded in the repository. Daisy Bell (1892)
and *Come Josephine in My Flying Machine* (1910, Fred Fisher / Alfred Bryan)
qualify. The 1952 King/Stewart/Price composition *You Belong to Me* is not
used; changing its words would not make its melody available.

The Come Josephine chorus was transcribed from the original 1910 C-major,
3/4, Waltz Moderato score held by
[Smithsonian Libraries](https://library.si.edu/digital-library/book/comejosephinemy00fishc),
not reconstructed from memory. Its answering verse is original to this
project and reuses the score's notes and timing without changing the melody.
The instrumental score, harmony, introduction, tempo, and pitch classes remain
in that register. Its vocal carrier is rendered one octave lower so the melody
fits Sable's established voice register without altering the music.

## Shared singing engine

`assistant/voice/offline_voice.py` represents a performance as a frozen
`Song` containing:

```python
name, score, eighth_seconds, harmony, chords,
intro_melody, cache_path, accompaniment_gain, vocal_semitones
```

A score item is `(syllable, midi_note, duration_in_eighths)`; a rest is
`(None, None, duration)`. One measure is six eighth-note units. The generic
builder, mixer, cache, and `sing(song, ...)` path are shared by every song.
`sing_daisy_bell()` remains as a compatibility wrapper.

Each fixed performance has an independent, versioned, voice-bound cache path
and accompaniment gain in `assistant/core/config.py`. Changing a score, tempo,
mix, intro, or voice identity requires a cache-version bump so an older WAV
cannot hide the change.

`assistant/voice/session.py` carries one trusted song key or validated `Song`
from the command registry into the audio loop. `assistant/main.py` resolves
fixed keys through the registry and displays the actual song name during
preparation, singing, completion, and failure. Natural wording is mapped by
trusted rules before any model call.

## Come Josephine

The fixed performance is:

1. one instrumental statement of the complete 32-measure tune (about 34.5
   seconds);
2. the public-domain chorus;
3. a two-measure bridge;
4. an original answering verse on the identical note/duration shape; and
5. a final whole measure.

Its accompaniment has one chord for every measure of the complete
performance. Phonetic spellings such as `ma`/`sheen` and `an`/`sir` are
deliberate because Piper synthesizes isolated sung syllables.

Typed and natural forms route to the same fixed command:

```text
sing come josephine
Could you perform Come Josephine in my flying machine?
```

## `sing what you want`

The director writes words; trusted Python owns all music. The two offered
templates are the unchanged Daisy Bell and Come Josephine chorus melodies.
The model cannot choose or modify pitches, durations, rests, chords, cache
paths, commands, or session state.

The pure generator in `assistant/voice/freestyle_song.py` receives a subject
and the trusted vocal-slot counts. It requests exactly one JSON object with
only `tune`, `title`, and `words`. Daisy requires 50 vocal tokens and
Josephine requires 69. Every token must be a bounded ASCII phonetic
monosyllable made only from letters, apostrophes, or hyphens.

The vendored llama.cpp server receives a JSON schema that constrains decoding
to those three fields, one trusted tune, its exact array length, and tokens
with one contiguous vowel group. This prevents malformed or short arrays from
being sampled; it does not replace the independent Python validation below.

Trusted validation rejects malformed or duplicate-key JSON, unknown tunes,
extra or missing fields, wrong counts, markup, controls, oversized values,
and multi-syllable tokens. It makes at most one repair request, using a closed
reason that cannot echo a model-invented field back as an instruction. If the
second reply is invalid, the command reports the failure and queues no audio.

The model transport is loopback-only, ignores proxy environment variables,
and refuses redirects before sending the subject or director credential. The
audio boundary then revalidates the complete frozen draft instead of trusting
its type or its caller. A valid draft replaces only vocal text on the chosen
fixed score.

Generated WAVs are content-addressed by tune, title, and validated words.
Repeated lyrics therefore reuse their render, while a rolling cache limit
(eight by default, configurable up to 32) prevents unbounded disk growth.

The obsolete experimental adaptive fitter was not shipped. It merged and
subdivided notes to accommodate approximate lines, which conflicted with the
active promise that notes and timing remain fixed. Its rationale and measured
trade-offs remain preserved in the singing handoff.

### Bounded limitation

The lyric call is synchronous. Each local request has a 120-second timeout and
there are at most two attempts, but Escape cancellation begins only once
rendering or playback starts. The musical duration itself cannot run away:
the two fixed choices are about 108 seconds (Daisy) and 70 seconds
(Josephine), including their instrumental introductions.

## Commands

```text
sing daisy bell
sing come josephine
sing what you want
sing what you want about <subject>
```

All three require a ready offline voice installation. Freestyle additionally
uses the already-running local director, but no cloud service.

## Verification

Focused automated coverage checks:

- the exact 32-bar Josephine transcription;
- identical notes/timing across its chorus and original answer;
- whole-measure intros and complete chord coverage;
- fixed and natural command routing, status text, and speaking indicator;
- strict JSON, duplicate fields, bounded repair, prompt-as-data behavior, and
  transport failures;
- revalidation at the audio boundary;
- unchanged notes/durations after lyric substitution;
- content-bound cache identities and cache pruning; and
- failure paths that queue neither audio mode nor a partial song.

Run from the `assistant` directory with an isolated test state:

```text
python -m unittest tests.test_freestyle_song tests.test_singing_easter_egg
```

Do not describe either performance as aurally or hardware validated until a
person has listened to the first uncached render and completed the four-case
Windows display/audio matrix: sleep/wake, lock/unlock, output switching, and
HDMI/DisplayPort disconnect/reconnect.
