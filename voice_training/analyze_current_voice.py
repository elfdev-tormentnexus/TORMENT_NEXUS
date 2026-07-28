"""Compare the active TORMENT_NEXUS speech chain with a supplied reference.

This is an offline measurement helper.  It renders one ordinary spoken reply
through the same Piper and robot-processing path used by the application, then
extracts timing, pitch and spectral summaries from that output and a reference
MP3.  The comparison is stylistic rather than word-aligned: the two recordings
say different things, so a metric describes delivery traits, not accuracy.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import math
import os
import subprocess
import sys
import wave


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSISTANT = os.path.join(ROOT, "assistant")
sys.path.insert(0, ASSISTANT)

import numpy as np


SAMPLE_TEXT = (
    "System check complete. I have considered the evidence, and the next "
    "decision is yours. Continue when you are ready."
)
TARGET_RATE = 16_000
FRAME = 640  # 40 ms, suitable for F0 estimates down to roughly 70 Hz.
HOP = 160    # 10 ms.


def read_wav_bytes(payload: bytes):
    with wave.open(io.BytesIO(payload), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    if width != 2:
        raise RuntimeError(f"Expected 16-bit Piper WAV, received {width * 8}-bit audio")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return samples.astype(np.float32) / 32768.0, rate


def resample(audio: np.ndarray, source_rate: int, target_rate: int = TARGET_RATE):
    if source_rate == target_rate:
        return audio.astype(np.float32, copy=False)
    target_len = max(1, int(round(len(audio) * target_rate / source_rate)))
    old_x = np.linspace(0.0, 1.0, len(audio), endpoint=False)
    new_x = np.linspace(0.0, 1.0, target_len, endpoint=False)
    return np.interp(new_x, old_x, audio).astype(np.float32)


def decode_reference(path: str, ffmpeg: str | None = None):
    """Decode a reference recording without requiring a system ffmpeg."""
    try:
        import soundfile as sf

        audio, rate = sf.read(path, always_2d=True, dtype="float32")
        mono = audio.mean(axis=1)
        if rate % TARGET_RATE == 0:
            return mono[::rate // TARGET_RATE].astype(np.float32)
        return resample(mono, rate)
    except Exception as soundfile_error:
        if not ffmpeg:
            raise RuntimeError(
                "Could not decode the reference with soundfile. Supply "
                "--ffmpeg only if a compatible local executable is available."
            ) from soundfile_error

    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        path,
        "-ac",
        "1",
        "-ar",
        str(TARGET_RATE),
        "-f",
        "f32le",
        "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Could not decode the reference MP3: {detail}")
    audio = np.frombuffer(result.stdout, dtype=np.float32)
    if not len(audio):
        raise RuntimeError("The reference MP3 decoded to no audio samples")
    return audio


def render_current(text: str = SAMPLE_TEXT):
    from piper import PiperVoice
    from piper.config import SynthesisConfig

    from core.config import (
        VOICE_CADENCE_STRENGTH,
        VOICE_PITCH_FLATTEN,
        VOICE_PITCH_SEMITONES,
        VOICE_ROBOT_FORMANT_SHIFT,
        VOICE_ROBOT_STRENGTH,
        VOICE_SPEECH_CARRIER_HZ,
        VOICE_SPEECH_CLAUSE_PAUSE_SECONDS,
        VOICE_SPEECH_LENGTH_SCALE,
        VOICE_SPEECH_NOISE_SCALE,
        VOICE_SPEECH_NOISE_W_SCALE,
        VOICE_SPEECH_PAUSE_SECONDS,
        VOICE_TTS_MODEL,
        VOICE_TTS_SPEAKER,
        VOICE_VOWEL_STRETCH,
    )
    import voice.offline_voice as offline_voice

    voice = PiperVoice.load(VOICE_TTS_MODEL)
    configuration = SynthesisConfig(
        volume=0.94,
        length_scale=VOICE_SPEECH_LENGTH_SCALE,
        noise_scale=VOICE_SPEECH_NOISE_SCALE,
        noise_w_scale=VOICE_SPEECH_NOISE_W_SCALE,
        normalize_audio=True,
    )
    if VOICE_TTS_SPEAKER is not None:
        configuration.speaker_id = VOICE_TTS_SPEAKER

    segments = []
    sample_rate = None
    chunks = offline_voice._speech_chunks(text)

    for index, chunk in enumerate(chunks):
        chunk_config = configuration
        adjusted_scale = offline_voice._speech_length_scale_for_chunk(
            chunk,
            configuration.length_scale,
        )
        if abs(adjusted_scale - configuration.length_scale) > 1e-6:
            chunk_config = copy.copy(configuration)
            chunk_config.length_scale = adjusted_scale

        target = io.BytesIO()
        with wave.open(target, "wb") as handle:
            voice.synthesize_wav(chunk, handle, syn_config=chunk_config)

        raw, chunk_rate = read_wav_bytes(target.getvalue())
        if sample_rate is None:
            sample_rate = chunk_rate
        elif sample_rate != chunk_rate:
            raise RuntimeError("Piper changed sample rate during one reply")

        pitch_bias = offline_voice._utterance_pitch_bias(chunk)
        shaped = offline_voice._encoded_robot_effect(
            np,
            (raw * 32767.0).astype(np.int16),
            sample_rate,
            VOICE_ROBOT_STRENGTH,
            carrier_hz=(
                VOICE_SPEECH_CARRIER_HZ
                * (2.0 ** (pitch_bias / 12.0))
            ),
            formant_shift=VOICE_ROBOT_FORMANT_SHIFT,
            cadence_strength=VOICE_CADENCE_STRENGTH,
            pitch_offset=VOICE_PITCH_SEMITONES,
            vowel_stretch=VOICE_VOWEL_STRETCH,
            pitch_flatten=VOICE_PITCH_FLATTEN,
        )
        segments.append(np.asarray(shaped, dtype=np.float32) / 32768.0)

        if index + 1 < len(chunks):
            ends_sentence = chunk.rstrip().endswith((".", "!", "?", ":"))
            gap = (
                VOICE_SPEECH_PAUSE_SECONDS
                if ends_sentence
                else VOICE_SPEECH_CLAUSE_PAUSE_SECONDS
            )
            segments.append(np.zeros(
                max(1, int(round(gap * sample_rate))),
                dtype=np.float32,
            ))

    if not segments or sample_rate is None:
        return np.zeros(1, dtype=np.float32), TARGET_RATE

    return np.concatenate(segments), sample_rate


def write_wav(path: str, audio: np.ndarray, rate: int):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes((clipped * 32767.0).astype(np.int16).tobytes())


def frames(audio: np.ndarray, size: int = FRAME, hop: int = HOP):
    if len(audio) < size:
        return np.empty((0, size), dtype=np.float32)
    count = 1 + (len(audio) - size) // hop
    stride = audio.strides[0]
    return np.lib.stride_tricks.as_strided(
        audio,
        shape=(count, size),
        strides=(hop * stride, stride),
        writeable=False,
    ).copy()


def energy_track(audio: np.ndarray):
    batches = frames(audio)
    if not len(batches):
        return np.empty(0, dtype=np.float32)
    return np.sqrt(np.mean(batches * batches, axis=1) + 1e-12)


def estimate_f0(audio: np.ndarray, rate: int = TARGET_RATE):
    batches = frames(audio)
    if not len(batches):
        return np.empty(0, dtype=np.float32), np.empty(0, dtype=np.float32)
    rms = np.sqrt(np.mean(batches * batches, axis=1) + 1e-12)
    gate = max(float(np.percentile(rms, 35)) * 0.55, 0.004)
    window = np.hanning(FRAME).astype(np.float32)
    minimum_lag = int(rate / 300.0)
    maximum_lag = int(rate / 70.0)
    values = np.full(len(batches), np.nan, dtype=np.float32)
    confidence = np.zeros(len(batches), dtype=np.float32)

    for index, batch in enumerate(batches):
        if rms[index] < gate:
            continue
        signal = (batch - np.mean(batch)) * window
        norm = float(np.dot(signal, signal))
        if norm <= 1e-8:
            continue
        correlation = np.correlate(signal, signal, mode="full")[FRAME - 1:]
        normalized = correlation / norm
        region = normalized[minimum_lag:maximum_lag + 1]
        offset = int(np.argmax(region))
        score = float(region[offset])
        if score < 0.33:
            continue
        lag = minimum_lag + offset
        if 1 <= lag < len(normalized) - 1:
            left, centre, right = normalized[lag - 1:lag + 2]
            denominator = left - 2.0 * centre + right
            if abs(float(denominator)) > 1e-8:
                lag += 0.5 * float(left - right) / float(denominator)
        # A noisy autocorrelation peak can make parabolic refinement jump far
        # outside the candidate range.  Keep the estimate inside the exact
        # 70--300 Hz voice band the search used above.
        lag = float(np.clip(lag, minimum_lag, maximum_lag))
        frequency = rate / lag
        if 70.0 <= frequency <= 300.0:
            values[index] = frequency
        confidence[index] = score
    return values, confidence


def contiguous_lengths(mask: np.ndarray):
    lengths = []
    start = None
    for index, enabled in enumerate(mask):
        if enabled and start is None:
            start = index
        elif not enabled and start is not None:
            lengths.append(index - start)
            start = None
    if start is not None:
        lengths.append(len(mask) - start)
    return lengths


def metrics(audio: np.ndarray, rate: int = TARGET_RATE):
    energy = energy_track(audio)
    f0, confidence = estimate_f0(audio, rate)
    voiced = f0[np.isfinite(f0)]
    output = {
        "duration_s": round(len(audio) / rate, 3),
        "voiced_frames_pct": 0.0,
        "f0_hz_median": None,
        "f0_range_10_90_hz": None,
        "f0_variation_st": None,
        "near_static_pitch_pct": None,
        "median_group_s": None,
        "median_pause_s": None,
        "spectral_centroid_hz": None,
        "pitch_confidence": None,
    }
    if len(f0):
        output["voiced_frames_pct"] = round(100.0 * len(voiced) / len(f0), 1)
    if len(voiced):
        median = float(np.median(voiced))
        semitones = 12.0 * np.log2(voiced / median)
        output["f0_hz_median"] = round(median, 1)
        output["f0_range_10_90_hz"] = [
            round(float(np.percentile(voiced, 10)), 1),
            round(float(np.percentile(voiced, 90)), 1),
        ]
        output["f0_variation_st"] = round(float(np.std(semitones)), 2)
        diffs = np.abs(np.diff(semitones))
        output["near_static_pitch_pct"] = round(
            100.0 * float(np.mean(diffs <= 0.20)), 1
        ) if len(diffs) else 100.0
        output["pitch_confidence"] = round(
            float(np.nanmedian(confidence[np.isfinite(f0)])), 2
        )

    if len(energy):
        threshold = max(float(np.percentile(energy, 35)) * 0.82, 0.003)
        active = energy >= threshold
        groups = [length * HOP / rate for length in contiguous_lengths(active)]
        pauses = [length * HOP / rate for length in contiguous_lengths(~active)]
        groups = [value for value in groups if value >= 0.08]
        pauses = [value for value in pauses if value >= 0.08]
        if groups:
            output["median_group_s"] = round(float(np.median(groups)), 3)
        if pauses:
            output["median_pause_s"] = round(float(np.median(pauses)), 3)

        window = np.hanning(FRAME).astype(np.float32)
        magnitude = np.abs(np.fft.rfft(frames(audio) * window, axis=1))
        frequencies = np.fft.rfftfreq(FRAME, 1.0 / rate)
        power = np.sum(magnitude, axis=1) + 1e-9
        centroids = (magnitude * frequencies).sum(axis=1) / power
        output["spectral_centroid_hz"] = round(float(np.median(centroids)), 1)
    return output


def best_excerpt(audio: np.ndarray, seconds: float = 10.0):
    window = int(seconds * TARGET_RATE)
    if len(audio) <= window:
        return audio, 0.0
    # The supplied reference collections can run for tens of minutes. Their
    # 40ms analysis frames would duplicate several hundred megabytes merely
    # to locate one excerpt, so use non-overlapping 10ms RMS blocks here.
    # Full overlapping frames are still used below for the selected excerpt.
    usable = len(audio) // HOP
    blocks = audio[:usable * HOP].reshape(usable, HOP)
    energy = np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-12)
    width = max(1, int(seconds * TARGET_RATE / HOP))
    if len(energy) <= width:
        return audio[:window], 0.0
    score = np.convolve(energy, np.ones(width, dtype=np.float32), mode="valid")
    start_frame = int(np.argmax(score))
    start = start_frame * HOP
    return audio[start:start + window], start / TARGET_RATE


def spectrogram(audio: np.ndarray, rate: int = TARGET_RATE, bins: int = 72, columns: int = 120):
    batches = frames(audio, 512, 160)
    if not len(batches):
        return []
    magnitude = np.abs(np.fft.rfft(batches * np.hanning(512), axis=1))
    maximum_bin = int(4_000 * 512 / rate)
    db = 20.0 * np.log10(magnitude[:, :maximum_bin + 1] + 1e-6)
    db -= float(np.max(db))
    db = np.clip(db, -70.0, 0.0)
    frequency_index = np.linspace(0, db.shape[1] - 1, bins).astype(int)
    time_index = np.linspace(0, db.shape[0] - 1, columns).astype(int)
    compact = db[np.ix_(time_index, frequency_index)]
    return np.rint(compact).astype(int).tolist()


def pitch_track(audio: np.ndarray):
    values, _ = estimate_f0(audio)
    selected = np.linspace(0, max(0, len(values) - 1), min(120, len(values))).astype(int)
    return [None if not math.isfinite(float(values[i])) else round(float(values[i]), 1) for i in selected]


def write_visual(path: str, report: dict):
    """Write the compact, in-conversation spectrogram comparison fragment."""
    spectrum = report["spectrogram"]
    data = {
        "reference_excerpt_start_s": report["reference_excerpt_start_s"],
        "reference_db": spectrum["reference_db"],
        "torment_nexus_db": spectrum["torment_nexus_db"],
        "reference_pitch_hz": spectrum["reference_pitch_hz"],
        "torment_nexus_pitch_hz": spectrum["torment_nexus_pitch_hz"],
    }
    payload = json.dumps(data, separators=(",", ":"))
    html = f'''<div id="voice-spectrogram-comparison">
  <div class="viz-grid">
    <figure>
      <figcaption>Reference speech — strongest 10 s excerpt, beginning at {data["reference_excerpt_start_s"]} s</figcaption>
      <canvas id="reference-spectrum" role="img" aria-label="Reference speech spectrogram from 0 to 4 kilohertz"></canvas>
      <div class="text-small text-muted">Time → · frequency 0–4 kHz ↑</div>
    </figure>
    <figure>
      <figcaption>TORMENT_NEXUS — current normal speech render</figcaption>
      <canvas id="torment-spectrum" role="img" aria-label="TORMENT_NEXUS normal speech spectrogram from 0 to 4 kilohertz"></canvas>
      <div class="text-small text-muted">Time → · frequency 0–4 kHz ↑</div>
    </figure>
  </div>
  <figure>
    <figcaption>Estimated pitch trajectory — gaps are unvoiced consonants or pauses</figcaption>
    <canvas id="pitch-comparison" role="img" aria-label="Pitch trajectory comparison"></canvas>
    <div class="text-small text-muted">Hz · solid = reference · dashed = TORMENT_NEXUS</div>
  </figure>
</div>
<script>
(() => {{
  const root = document.getElementById("voice-spectrogram-comparison");
  const data = {payload};
  function fit(canvas, height) {{
    const width = Math.max(280, Math.floor(canvas.parentElement.clientWidth || 340));
    const scale = window.devicePixelRatio || 1;
    canvas.width = width * scale; canvas.height = height * scale;
    canvas.style.width = width + "px"; canvas.style.height = height + "px";
    const context = canvas.getContext("2d");
    context.setTransform(scale, 0, 0, scale, 0, 0);
    return {{ context, width, height }};
  }}
  function color(db) {{
    const t = Math.max(0, Math.min(1, (db + 70) / 70));
    return "rgb(" + Math.round(30 + 220 * t) + "," + Math.round(20 + 140 * Math.pow(t, 1.6)) + "," + Math.round(45 + 90 * (1 - t)) + ")";
  }}
  function drawSpectrum(canvas, values) {{
    const {{ context, width, height }} = fit(canvas, 170);
    const cellW = width / values.length, cellH = height / values[0].length;
    context.clearRect(0, 0, width, height);
    values.forEach((column, x) => column.forEach((db, y) => {{
      context.fillStyle = color(db);
      context.fillRect(x * cellW, height - (y + 1) * cellH, Math.ceil(cellW), Math.ceil(cellH));
    }}));
  }}
  function drawPitch() {{
    const canvas = root.querySelector("#pitch-comparison");
    const {{ context, width, height }} = fit(canvas, 145);
    const all = [...data.reference_pitch_hz, ...data.torment_nexus_pitch_hz].filter(value => value !== null);
    const min = Math.floor(Math.min(...all) / 20) * 20, max = Math.ceil(Math.max(...all) / 20) * 20;
    context.clearRect(0, 0, width, height);
    context.strokeStyle = "var(--border)"; context.lineWidth = 1;
    [min, (min + max) / 2, max].forEach(value => {{
      const y = height - 12 - ((value - min) / (max - min)) * (height - 28);
      context.beginPath(); context.moveTo(34, y); context.lineTo(width - 8, y); context.stroke();
      context.fillStyle = "var(--muted-foreground)"; context.font = "12px sans-serif"; context.fillText(Math.round(value) + " Hz", 0, y + 4);
    }});
    function line(values, stroke, dashed) {{
      context.strokeStyle = stroke; context.lineWidth = 2; context.setLineDash(dashed ? [5, 4] : []);
      let open = false;
      values.forEach((value, index) => {{
        if (value === null) {{ open = false; return; }}
        const x = 34 + index / Math.max(1, values.length - 1) * (width - 42);
        const y = height - 12 - ((value - min) / (max - min)) * (height - 28);
        if (!open) {{ context.beginPath(); context.moveTo(x, y); open = true; }} else context.lineTo(x, y);
        if (index === values.length - 1 || values[index + 1] === null) context.stroke();
      }});
      context.setLineDash([]);
    }}
    line(data.reference_pitch_hz, "var(--viz-series-1)", false);
    line(data.torment_nexus_pitch_hz, "var(--viz-series-2)", true);
  }}
  function draw() {{
    drawSpectrum(root.querySelector("#reference-spectrum"), data.reference_db);
    drawSpectrum(root.querySelector("#torment-spectrum"), data.torment_nexus_db);
    drawPitch();
  }}
  new ResizeObserver(draw).observe(root); draw();
}})();
</script>'''
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference")
    parser.add_argument(
        "--ffmpeg",
        help="Optional fallback decoder when soundfile cannot read the reference",
    )
    parser.add_argument("--text", default=SAMPLE_TEXT)
    parser.add_argument("--sample-name", default="torment_nexus_normal_speech_sample.wav")
    parser.add_argument(
        "--out",
        default=os.path.join(ROOT, "voice_training", "analysis"),
    )
    parser.add_argument("--visual")
    args = parser.parse_args()

    current, current_rate = render_current(args.text)
    current = resample(current, current_rate)
    reference = decode_reference(args.reference, args.ffmpeg)
    reference_excerpt, reference_start = best_excerpt(reference)
    current_excerpt, _ = best_excerpt(current)

    os.makedirs(args.out, exist_ok=True)
    current_wav = os.path.join(args.out, os.path.basename(args.sample_name))
    write_wav(current_wav, current, TARGET_RATE)

    report = {
        "sample_text": args.text,
        "reference_file": os.path.basename(args.reference),
        "reference_excerpt_start_s": round(reference_start, 2),
        "reference": metrics(reference_excerpt),
        "torment_nexus": metrics(current_excerpt),
        "spectrogram": {
            "frequency_max_hz": 4000,
            "reference_db": spectrogram(reference_excerpt),
            "torment_nexus_db": spectrogram(current_excerpt),
            "reference_pitch_hz": pitch_track(reference_excerpt),
            "torment_nexus_pitch_hz": pitch_track(current_excerpt),
        },
    }
    with open(os.path.join(args.out, "voice_comparison.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    if args.visual:
        write_visual(args.visual, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
