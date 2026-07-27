"""
Turn a single long recording into a Piper-ready training dataset.

Piper fine-tuning wants LJSpeech layout: a folder of short single-utterance
wavs plus a metadata.csv mapping each clip id to its transcript. This script
does the whole conversion:

    long recording -> utterance segmentation -> per-clip transcription
                   -> 22.05kHz mono 16-bit wavs + metadata.csv

Transcription reuses the Moonshine ASR model the assistant already ships
(models/voice/sherpa-onnx-moonshine-tiny-en-int8), so this needs no cloud
service and no new model download.

IMPORTANT: it is a *tiny* ASR model. Its transcripts are a starting point,
not ground truth. Training on wrong transcripts teaches the voice wrong
pronunciations, so proofread metadata.csv before training -- the script
flags the clips most likely to need attention.

Usage:
    python voice_training/prepare_dataset.py "path/to/recording.mp3"
    python voice_training/prepare_dataset.py "path/to/recording.mp3" --out dataset
"""

import argparse
import os
import sys
import wave

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ASSISTANT_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), "assistant")
sys.path.insert(0, ASSISTANT_DIR)

# Piper "medium" quality voices are trained at 22.05kHz. Matching the base
# checkpoint's rate matters -- resampling at training time would otherwise
# silently degrade the result.
TARGET_SR = 22_050

# Utterance length bounds. Very short clips carry too little signal to be
# worth a training step; very long ones blow up VRAM and are usually run-on
# speech that segmented badly.
MIN_SECONDS = 1.0
MAX_SECONDS = 14.0

# Silence detection. top_db is measured below the clip's peak, so a larger
# value treats quieter sound as speech.
SPLIT_TOP_DB = 32
MIN_PAUSE_SECONDS = 0.28


def load_audio(path):
    import librosa

    print(f"Loading {path} ...")
    audio, _ = librosa.load(path, sr=TARGET_SR, mono=True)
    print(f"  {len(audio) / TARGET_SR:.1f}s at {TARGET_SR} Hz")
    return audio


def segment(audio):
    """Split on silence, then break up anything still over MAX_SECONDS."""
    import librosa

    intervals = librosa.effects.split(
        audio,
        top_db=SPLIT_TOP_DB,
        frame_length=2048,
        hop_length=512,
    )

    max_samples = int(MAX_SECONDS * TARGET_SR)
    min_samples = int(MIN_SECONDS * TARGET_SR)
    refined = []

    for start, end in intervals:
        if end - start <= max_samples:
            refined.append((start, end))
            continue

        # Too long: cut at the quietest points rather than at fixed offsets,
        # so splits land between words instead of mid-syllable.
        cursor = start

        while end - cursor > max_samples:
            window_start = cursor + int(max_samples * 0.6)
            window_end = cursor + max_samples
            window = np.abs(audio[window_start:window_end])

            if not len(window):
                break

            # Smooth before picking the minimum so a single near-zero sample
            # in the middle of a word doesn't attract the cut.
            smooth = np.convolve(
                window,
                np.ones(int(0.02 * TARGET_SR)) / int(0.02 * TARGET_SR),
                mode="same",
            )
            cut = window_start + int(np.argmin(smooth))
            refined.append((cursor, cut))
            cursor = cut

        if end - cursor >= min_samples:
            refined.append((cursor, end))

    kept = [(s, e) for s, e in refined if (e - s) >= min_samples]
    dropped = len(refined) - len(kept)

    print(f"  {len(kept)} utterances (dropped {dropped} under {MIN_SECONDS}s)")
    return kept


def build_recognizer():
    import sherpa_onnx
    from core.config import VOICE_ASR_DIR, VOICE_NUM_THREADS

    path = lambda name: os.path.join(VOICE_ASR_DIR, name)

    return sherpa_onnx.OfflineRecognizer.from_moonshine(
        preprocessor=path("preprocess.onnx"),
        encoder=path("encode.int8.onnx"),
        uncached_decoder=path("uncached_decode.int8.onnx"),
        cached_decoder=path("cached_decode.int8.onnx"),
        tokens=path("tokens.txt"),
        num_threads=VOICE_NUM_THREADS,
        decoding_method="greedy_search",
        debug=False,
    )


def transcribe(recognizer, chunk):
    stream = recognizer.create_stream()
    stream.accept_waveform(TARGET_SR, chunk)
    recognizer.decode_stream(stream)
    return stream.result.text.strip()


def write_wav(path, samples):
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)

    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(TARGET_SR)
        handle.writeframes(pcm.tobytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("recording", help="Long source recording (mp3/wav/etc).")
    parser.add_argument(
        "--out",
        default=os.path.join(PROJECT_ROOT, "dataset"),
        help="Output dataset folder.",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.recording):
        parser.error(f"No such file: {args.recording}")

    wav_dir = os.path.join(args.out, "wavs")
    os.makedirs(wav_dir, exist_ok=True)

    audio = load_audio(args.recording)
    segments = segment(audio)

    if not segments:
        print("No usable utterances found. Try lowering SPLIT_TOP_DB.")
        return 1

    print("Loading ASR model ...")
    recognizer = build_recognizer()

    rows = []
    suspicious = []
    total_seconds = 0.0

    print("Transcribing ...")

    for index, (start, end) in enumerate(segments, start=1):
        chunk = audio[start:end]
        seconds = len(chunk) / TARGET_SR
        text = transcribe(recognizer, chunk)

        if not text:
            suspicious.append((index, seconds, "(empty transcript)"))
            continue

        clip_id = f"utt_{index:04d}"
        write_wav(os.path.join(wav_dir, clip_id + ".wav"), chunk)
        rows.append((clip_id, text))
        total_seconds += seconds

        # Rough sanity heuristic: English speech runs ~2-4 words/sec. Well
        # outside that usually means the ASR dropped or hallucinated words,
        # which is exactly what must not reach training unproofread.
        words_per_second = len(text.split()) / max(seconds, 0.01)

        if words_per_second < 1.2 or words_per_second > 5.0:
            suspicious.append((index, seconds, text))

        if index % 10 == 0:
            print(f"  {index}/{len(segments)} ...")

    metadata = os.path.join(args.out, "metadata.csv")

    with open(metadata, "w", encoding="utf-8", newline="") as handle:
        for clip_id, text in rows:
            handle.write(f"{clip_id}|{text}\n")

    print()
    print("=" * 58)
    print(f"Dataset written to {args.out}")
    print(f"  clips:          {len(rows)}")
    print(f"  total speech:   {total_seconds / 60:.1f} min")
    print(f"  mean clip:      {total_seconds / max(len(rows), 1):.1f}s")
    print(f"  metadata:       {metadata}")

    if suspicious:
        print()
        print(f"  {len(suspicious)} clip(s) worth checking first:")
        for index, seconds, text in suspicious[:15]:
            print(f"    utt_{index:04d} ({seconds:.1f}s): {text[:60]}")
        if len(suspicious) > 15:
            print(f"    ... and {len(suspicious) - 15} more")

    print()
    print("NEXT: proofread metadata.csv before training. The ASR is a tiny")
    print("model -- wrong transcripts teach the voice wrong pronunciations.")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
