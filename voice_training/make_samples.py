"""
Render listenable samples of the top-scoring candidate voices.

screen_voices.py ranks candidates on measurements, but the final call is a
judgement about character that no metric settles. This writes each finalist
through the real production chain -- same cadence, same declination, same
derived pacing -- so what you hear is what the assistant would actually
sound like, not a raw synthesis that flatters the voice.

Each candidate gets exactly the pitch shift it needs to land on the target
register and no more, which matters: the shift is what stretches time and
darkens formants, so a voice that is natively close pays almost none of
that cost.

Usage:
    python voice_training/make_samples.py
    python voice_training/make_samples.py --top 8
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

TARGET_F0 = 149.5

LINE = (
    "The disk is filling up again. I moved the old backups, but that only "
    "buys a few days. You should decide what actually needs keeping, "
    "before something decides for you."
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--scores", default=os.path.join(PROJECT_ROOT, "voice_scores.json"))
    parser.add_argument("--out", default=os.path.join(PROJECT_ROOT, "samples"))
    args = parser.parse_args()

    from piper import PiperVoice
    from piper.config import SynthesisConfig
    from core.config import (
        VOICE_MODEL_ROOT,
        VOICE_SPEECH_NOISE_SCALE,
        VOICE_SPEECH_NOISE_W_SCALE,
        VOICE_SPEECH_PACE,
        VOICE_ROBOT_STRENGTH,
        VOICE_CADENCE_STRENGTH,
    )
    import voice.offline_voice as ov

    with open(args.scores, encoding="utf-8") as handle:
        ranked = json.load(handle)

    os.makedirs(args.out, exist_ok=True)

    picks = ranked[:args.top]

    # Always include the incumbent, wherever it placed, so there is a
    # familiar reference point in the same folder.
    current = next(
        (r for r in ranked if r["model"] == "en_US-hfc_female-medium"),
        None,
    )

    if current and current not in picks:
        picks = picks + [current]

    loaded = {}
    print(f"Rendering {len(picks)} samples to {args.out}\n")

    for index, entry in enumerate(picks, start=1):
        model = entry["model"]

        if model not in loaded:
            loaded[model] = PiperVoice.load(
                os.path.join(VOICE_MODEL_ROOT, "piper", model + ".onnx")
            )

        voice = loaded[model]

        # Only shift as far as this voice actually needs.
        offset = 12 * np.log2(TARGET_F0 / entry["f0"])
        offset = float(np.clip(offset, -12.0, 12.0))
        stretch = 2.0 ** (-offset / 12.0)
        length_scale = max(0.5, VOICE_SPEECH_PACE / stretch)

        cfg = SynthesisConfig(
            volume=0.94,
            length_scale=length_scale,
            noise_scale=VOICE_SPEECH_NOISE_SCALE,
            noise_w_scale=VOICE_SPEECH_NOISE_W_SCALE,
            normalize_audio=True,
        )

        if entry["speaker"] is not None:
            cfg.speaker_id = entry["speaker"]

        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as handle:
            voice.synthesize_wav(LINE, handle, syn_config=cfg)

        buffer.seek(0)

        with wave.open(buffer, "rb") as handle:
            sr = handle.getframerate()
            raw = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)

        shaped = ov._encoded_robot_effect(
            np,
            raw,
            sr,
            VOICE_ROBOT_STRENGTH,
            cadence_strength=VOICE_CADENCE_STRENGTH,
            pitch_offset=offset,
        )

        speaker = "" if entry["speaker"] is None else f"_spk{entry['speaker']}"
        incumbent = " (CURRENT)" if entry is current else ""
        name = f"{index:02d}_{model}{speaker}.wav"

        with wave.open(os.path.join(args.out, name), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sr)
            handle.writeframes(np.asarray(shaped, dtype=np.int16).tobytes())

        print(
            f"  {name:44} native {entry['f0']:6.1f}Hz  "
            f"shift {offset:+5.2f}st  flatness {entry['stdev']:4.2f}st{incumbent}"
        )

    print(f"\nDone. Play them from {args.out}")


if __name__ == "__main__":
    raise SystemExit(main())
