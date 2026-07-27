"""
Rank Piper voices (and individual speakers inside multi-speaker models)
against the project's target voice profile.

The target is a cold, flat, unhurried machine voice. Rather than judging
that by ear across a thousand candidates, this measures four things that
correspond to what actually goes wrong:

    median F0        how low the resting pitch sits
    pitch stdev      how flat it is -- the single best predictor of
                     whether a voice reads as bored or as expressive
    peak over median how far the loudest stressed syllables spike up;
                     this is what gets heard as "squeaky"
    brightness       spectral centroid, how thin/clinical it sounds

Measured on RAW synthesis, deliberately. The processing chain applies a
constant shift afterwards, so a voice that is natively close to target
needs less correction -- and less correction means less of the formant
darkening that a large resampling shift causes.

Usage:
    python voice_training/screen_voices.py                  # all local voices
    python voice_training/screen_voices.py --limit 60       # cap speakers/model
    python voice_training/screen_voices.py --top 25
"""

import argparse
import io
import json
import os
import sys
import warnings
import wave

warnings.filterwarnings("ignore")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(PROJECT_ROOT), "assistant"))

import numpy as np

# Measured from the reference recording -- see the session that produced
# these numbers; they are not guesses.
TARGET_F0 = 149.5
TARGET_BRIGHTNESS = 1822.0

# Short on purpose: this runs once per speaker, and there are ~1000.
PHRASE = "You should decide what actually needs keeping."


def measure(audio, sr, librosa):
    y = np.asarray(audio, dtype=np.float32)

    if y.ndim > 1:
        y = y.mean(axis=1)

    if np.max(np.abs(y)) > 1.5:
        y = y / 32768.0

    if np.max(np.abs(y)) < 1e-4:
        return None

    f0, _, _ = librosa.pyin(
        y, fmin=50, fmax=500, sr=sr, frame_length=1024
    )
    voiced = f0[~np.isnan(f0)]

    if len(voiced) < 12:
        return None

    median = float(np.median(voiced))
    semitones = 12 * np.log2(voiced / median)
    spectrum = np.abs(librosa.stft(y, n_fft=1024))

    return {
        "f0": median,
        "stdev": float(np.std(semitones)),
        "peak": float(12 * np.log2(np.percentile(voiced, 95) / median)),
        "brightness": float(
            np.mean(librosa.feature.spectral_centroid(S=spectrum, sr=sr)[0])
        ),
    }


def score(m):
    """
    Lower is better. Flatness is weighted hardest because that is the
    complaint the ear keeps returning to, and because pitch is the one
    property the processing chain can still correct afterwards.
    """
    return (
        abs(12 * np.log2(m["f0"] / TARGET_F0)) * 1.0
        + m["stdev"] * 2.0
        + m["peak"] * 1.5
        + abs(m["brightness"] - TARGET_BRIGHTNESS) / 400.0
    )


def synthesize(voice, syn_config, speaker_id=None):
    target = io.BytesIO()

    with wave.open(target, "wb") as handle:
        if speaker_id is None:
            voice.synthesize_wav(PHRASE, handle, syn_config=syn_config)
        else:
            syn_config.speaker_id = speaker_id
            voice.synthesize_wav(PHRASE, handle, syn_config=syn_config)

    target.seek(0)

    with wave.open(target, "rb") as handle:
        sr = handle.getframerate()
        frames = handle.readframes(handle.getnframes())

    return np.frombuffer(frames, dtype=np.int16), sr


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Max speakers to test per multi-speaker model.")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", default=os.path.join(PROJECT_ROOT, "voice_scores.json"))
    args = parser.parse_args()

    import librosa
    from piper import PiperVoice
    from piper.config import SynthesisConfig
    from core.config import VOICE_MODEL_ROOT, VOICE_SPEECH_NOISE_SCALE, \
        VOICE_SPEECH_NOISE_W_SCALE, VOICE_SPEECH_LENGTH_SCALE

    folder = os.path.join(VOICE_MODEL_ROOT, "piper")
    models = sorted(
        f[:-5] for f in os.listdir(folder) if f.endswith(".onnx")
    )

    print(f"Found {len(models)} local voice model(s): {', '.join(models)}")
    print()

    results = []

    for name in models:
        path = os.path.join(folder, name + ".onnx")
        voice = PiperVoice.load(path)

        with open(path + ".json", encoding="utf-8") as handle:
            meta = json.load(handle)

        speakers = meta.get("num_speakers", 1) or 1
        ids = [None] if speakers <= 1 else list(range(speakers))

        if args.limit and len(ids) > args.limit:
            # Even spread rather than the first N, so the sample is not
            # biased toward however the dataset happened to be ordered.
            step = len(ids) / args.limit
            ids = [ids[int(i * step)] for i in range(args.limit)]

        print(f"{name}: testing {len(ids)} speaker(s) ...")

        for index, speaker_id in enumerate(ids, start=1):
            cfg = SynthesisConfig(
                volume=0.94,
                length_scale=VOICE_SPEECH_LENGTH_SCALE,
                noise_scale=VOICE_SPEECH_NOISE_SCALE,
                noise_w_scale=VOICE_SPEECH_NOISE_W_SCALE,
                normalize_audio=True,
            )

            try:
                audio, sr = synthesize(voice, cfg, speaker_id)
                m = measure(audio, sr, librosa)
            except Exception:
                continue

            if not m:
                continue

            m["model"] = name
            m["speaker"] = speaker_id
            m["score"] = score(m)
            results.append(m)

            if index % 50 == 0:
                print(f"   {index}/{len(ids)} ...")

    results.sort(key=lambda r: r["score"])

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    print()
    print("=" * 96)
    print(f"TARGET{'':22}F0 {TARGET_F0:6.1f}Hz  flat -> low   peak -> low   "
          f"bright {TARGET_BRIGHTNESS:5.0f}Hz")
    print("=" * 96)
    print(f"{'rank':<5}{'voice':<34}{'F0':>8}{'stdev':>8}{'peak':>8}{'bright':>9}{'score':>8}")

    for rank, r in enumerate(results[:args.top], start=1):
        label = r["model"] + (f" #{r['speaker']}" if r["speaker"] is not None else "")
        print(f"{rank:<5}{label:<34}{r['f0']:7.1f}H{r['stdev']:7.2f}s"
              f"{r['peak']:7.2f}s{r['brightness']:8.0f}H{r['score']:8.2f}")

    print()
    print(f"Full ranking of {len(results)} candidates written to {args.out}")


if __name__ == "__main__":
    raise SystemExit(main())
