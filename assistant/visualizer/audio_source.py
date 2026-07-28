"""
System-audio capture and frequency analysis for the music visualizer.

Captures what the machine is *playing* rather than what a microphone
hears, so the visualiser reacts to a browser tab, a music player, or a
local file identically without knowing anything about any of them. That
is deliberate: no per-site extractor to maintain and nothing to break
when a site changes.

Uses `soundcard` rather than `sounddevice`, which the rest of the project
uses for speech. sounddevice's WasapiSettings has no loopback option
(verified against 0.5.5: exclusive, auto_convert, explicit_sample_format
only), so it cannot capture playback on Windows at all. soundcard exposes
loopback on both WASAPI and PulseAudio, which covers the dev machine and
the Pi with one code path.

Everything degrades quietly. If capture cannot start, features() keeps
returning zeros and the visualiser animates at rest instead of taking
the mode down.
"""

from collections import deque
import math
import threading
import time


SAMPLE_RATE = 44_100
BLOCK = 1024

# ~21 Hz per bin. The signal is short enough to feel immediate; the onset
# detector compares successive overlapping windows, rather than waiting for a
# slower tempo estimate, so kick transients still land promptly.
WINDOW = 2048
WAVEFORM_POINTS = 128
SPECTRUM_BINS = 48

# Bass drives expansion, mids drive motion, and treble drives fine detail.
# Keeping them separate makes a kick pulse the tunnel while a hi-hat adds
# narrow electric contours.
BANDS = {
    "bass": (20.0, 250.0),
    "mid": (250.0, 2_000.0),
    "treble": (2_000.0, 8_000.0),
}

# Detection is narrower than the display's bass meter.  Ignoring the first
# 35 Hz rejects DC, fan rumble, and desktop noise while retaining 808s and
# ordinary kick drums.
KICK_BAND = (35.0, 180.0)
ONSET_BAND = (30.0, 8_000.0)
GAIN_RELEASE_SECONDS = 1.6
BASS_ATTACK_SECONDS = 0.025
BASS_RELEASE_SECONDS = 0.18
BEAT_RELEASE_SECONDS = 0.11
BEAT_REFRACTORY_SECONDS = 0.115
ONSET_HISTORY_SECONDS = 1.5

SILENT = {
    "bass": 0.0,
    "mid": 0.0,
    "treble": 0.0,
    "level": 0.0,
    "beat": 0.0,
    "stereo_width": 0.0,
    "pan": 0.0,
    "sub_bass": 0.0,
    "kick": 0.0,
    "onset": 0.0,
    "waveform": (),
    "spectrum": (),
}


class AudioSource:
    def __init__(self):
        self.error = None
        self.device_name = None
        self._thread = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._np = None
        self._buffer = None
        self._stereo_buffer = None
        self._window = None
        self._spectrum_smooth = None
        self._freqs = None
        self._band_masks = None
        self._sub_bass_mask = None
        self._kick_mask = None
        self._onset_mask = None

        # Per-band decaying ceilings keep the display legible at any volume.
        # Their release is time-based so the same song behaves consistently
        # at a slow terminal redraw and in a fast visualizer frame.
        self._ceiling = {name: 1e-6 for name in BANDS}
        self._smooth = {name: 0.0 for name in BANDS}
        self.beat = 0.0
        self._prev_log_spectrum = None
        self._onset_history = deque()
        self._last_feature_at = None
        self._last_onset_at = float("-inf")

    # -- lifecycle -------------------------------------------------------

    def start(self):
        try:
            import numpy as np
            import soundcard
        except Exception as error:
            self.error = (
                f"Music mode needs numpy and soundcard: {error}\n"
                "Install with: pip install soundcard"
            )
            return False

        self._np = np
        self._buffer = np.zeros(WINDOW, dtype=np.float32)
        self._stereo_buffer = np.zeros((WINDOW, 2), dtype=np.float32)
        self._window = np.hanning(WINDOW).astype(np.float32)
        self._spectrum_smooth = np.zeros(SPECTRUM_BINS, dtype=np.float32)
        self._prepare_analysis_state()

        try:
            microphone = self._loopback_device(soundcard)
        except Exception as error:
            self.error = str(error)
            return False

        self.device_name = microphone.name
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(microphone,),
            daemon=True,
        )
        self._thread.start()

        # Wait only until the recorder either opens or reports an immediate
        # failure. The old thread.join(timeout=1.2) always waited the full
        # timeout because a healthy capture thread is intentionally long-lived.
        self._ready.wait(timeout=1.2)

        if self.error:
            return False

        return True

    def stop(self):
        self._stop.set()
        thread, self._thread = self._thread, None

        if thread is not None:
            thread.join(timeout=1.5)

    @staticmethod
    def _loopback_device(soundcard):
        """A capture handle that hears the default output."""
        speaker = soundcard.default_speaker()

        try:
            return soundcard.get_microphone(
                id=str(speaker.name),
                include_loopback=True,
            )
        except Exception:
            pass

        # PulseAudio/PipeWire name these explicitly.
        for microphone in soundcard.all_microphones(include_loopback=True):
            if "monitor" in microphone.name.lower():
                return microphone

        raise RuntimeError(
            "No loopback capture device found.\n"
            "On Linux/Pi, PulseAudio exposes outputs as '.monitor' sources; "
            "enable one with: pactl load-module module-loopback"
        )

    def _capture_loop(self, microphone):
        np = self._np

        try:
            with microphone.recorder(
                samplerate=SAMPLE_RATE,
                channels=2,
                blocksize=BLOCK,
            ) as recorder:
                self._ready.set()
                while not self._stop.is_set():
                    block = np.asarray(
                        recorder.record(numframes=BLOCK),
                        dtype=np.float32,
                    )

                    if block.ndim == 1:
                        block = block.reshape(-1, 1)

                    if block.shape[1] == 1:
                        stereo = np.repeat(block, 2, axis=1)
                    else:
                        stereo = block[:, :2]

                    mono = stereo.mean(axis=1)
                    count = len(mono)

                    if not count:
                        continue

                    with self._lock:
                        if count >= WINDOW:
                            self._buffer[:] = mono[-WINDOW:]
                            self._stereo_buffer[:] = stereo[-WINDOW:]
                        else:
                            self._buffer[:-count] = self._buffer[count:]
                            self._buffer[-count:] = mono
                            self._stereo_buffer[:-count] = (
                                self._stereo_buffer[count:]
                            )
                            self._stereo_buffer[-count:] = stereo
        except Exception as error:
            self.error = f"System audio capture stopped: {error}"
            self._ready.set()

    # -- analysis --------------------------------------------------------

    def _prepare_analysis_state(self):
        """Build FFT masks and clear state that belongs to one capture run."""
        np = self._np
        self._freqs = np.fft.rfftfreq(WINDOW, 1.0 / SAMPLE_RATE)
        self._band_masks = {
            name: (self._freqs >= low) & (self._freqs < high)
            for name, (low, high) in BANDS.items()
        }
        self._sub_bass_mask = (
            (self._freqs >= 35.0)
            & (self._freqs < 75.0)
        )
        self._kick_mask = (
            (self._freqs >= KICK_BAND[0])
            & (self._freqs < KICK_BAND[1])
        )
        self._onset_mask = (
            (self._freqs >= ONSET_BAND[0])
            & (self._freqs < ONSET_BAND[1])
        )
        self._ceiling = {name: 1e-6 for name in BANDS}
        self._smooth = {name: 0.0 for name in BANDS}
        self.beat = 0.0
        self._prev_log_spectrum = None
        self._onset_history.clear()
        self._last_feature_at = None
        self._last_onset_at = float("-inf")

    def _ensure_analysis_state(self):
        if self._freqs is None or self._band_masks is None:
            self._prepare_analysis_state()

        if self._spectrum_smooth is None:
            self._spectrum_smooth = self._np.zeros(
                SPECTRUM_BINS,
                dtype=self._np.float32,
            )

    def _feature_delta(self, now):
        previous, self._last_feature_at = self._last_feature_at, now

        if previous is None:
            return BLOCK / float(SAMPLE_RATE)

        return max(0.01, min(0.25, now - previous))

    @staticmethod
    def _rate_alpha(delta, seconds):
        return 1.0 - math.exp(-max(0.0, delta) / max(0.001, seconds))

    def _update_onset(self, log_spectrum, now, delta):
        """Return a one-shot, adaptive kick/onset envelope from spectral flux."""
        np = self._np
        previous = self._prev_log_spectrum
        self._prev_log_spectrum = log_spectrum.copy()

        if previous is None or previous.shape != log_spectrum.shape:
            # Seed a baseline before looking for change. This avoids treating
            # the first capture buffer (which may include device noise) as a
            # kick, while an actual silent gap supplies an explicit zero
            # baseline below.
            self._onset_history.append((now, 0.0))
            return self.beat

        kick_flux = float(np.mean(np.maximum(
            log_spectrum[self._kick_mask] - previous[self._kick_mask],
            0.0,
        )))
        wide_flux = float(np.mean(np.maximum(
            log_spectrum[self._onset_mask] - previous[self._onset_mask],
            0.0,
        )))
        novelty = kick_flux * 0.85 + wide_flux * 0.15

        cutoff = now - ONSET_HISTORY_SECONDS
        while self._onset_history and self._onset_history[0][0] < cutoff:
            self._onset_history.popleft()

        history = np.asarray(
            [value for _stamp, value in self._onset_history],
            dtype=np.float32,
        )
        baseline = float(np.median(history)) if history.size else 0.0
        spread = (
            float(np.median(np.abs(history - baseline)))
            if history.size else 0.0
        )
        threshold = max(0.003, baseline + 3.25 * spread)
        self._onset_history.append((now, novelty))

        triggered = (
            novelty > threshold
            and kick_flux > max(0.0015, wide_flux * 0.75)
            and now - self._last_onset_at >= BEAT_REFRACTORY_SECONDS
        )

        self.beat *= math.exp(-max(0.0, delta) / BEAT_RELEASE_SECONDS)

        if triggered:
            strength = min(
                1.0,
                (novelty - threshold) / max(threshold, 1e-6),
            )
            self.beat = max(self.beat, 0.45 + 0.55 * strength)
            self._last_onset_at = now

        return self.beat

    def features(self):
        """
        Current audio shape, values roughly 0..1:

            bass / mid / treble   auto-gained band energy
            level                 overall loudness
            beat                  spike on a bass onset

        Zeros when nothing is playing, which the visualiser treats as
        idle rather than as an error.
        """
        if (
            self._np is None
            or self._buffer is None
            or self._stereo_buffer is None
        ):
            return dict(SILENT)

        np = self._np
        now = time.monotonic()
        delta = self._feature_delta(now)
        self._ensure_analysis_state()

        with self._lock:
            samples = self._buffer.copy()
            stereo = self._stereo_buffer.copy()

        if not np.any(samples):
            self.beat *= math.exp(-delta / BEAT_RELEASE_SECONDS)
            # Compare the next audible frame with a genuinely quiet spectrum.
            # Resetting this to ``None`` discarded the very first kick after a
            # silent gap because it had no predecessor to create flux against.
            self._prev_log_spectrum = np.zeros(
                WINDOW // 2 + 1,
                dtype=np.float32,
            )
            self._onset_history.append((now, 0.0))
            cutoff = now - ONSET_HISTORY_SECONDS
            while (
                self._onset_history
                and self._onset_history[0][0] < cutoff
            ):
                self._onset_history.popleft()
            quiet = dict(SILENT)
            quiet["beat"] = self.beat
            return quiet

        spectrum = np.abs(np.fft.rfft(samples * self._window))
        power = spectrum * spectrum
        freqs = self._freqs
        # This is deliberately a *sum*, not a mean: it measures how much of
        # the audible spectrum actually belongs to a band.  It stops a tiny
        # FFT side-lobe from a cymbal or voice being auto-gained until it looks
        # like full-strength bass.
        analysis_power = max(
            1e-12,
            float(np.sum(power[self._onset_mask])),
        )
        out = {}
        raw_level = float(np.sqrt(np.mean(samples ** 2)))
        level = min(1.0, raw_level * 6.0)

        for name in BANDS:
            mask = self._band_masks[name]
            band_power = float(np.sum(power[mask])) if mask.any() else 0.0
            energy = (
                math.sqrt(band_power / max(1, int(np.count_nonzero(mask))))
                if band_power
                else 0.0
            )

            self._ceiling[name] = max(
                self._ceiling[name] * math.exp(-delta / GAIN_RELEASE_SECONDS),
                energy,
                1e-6,
            )
            value = min(1.0, energy / self._ceiling[name])
            # Preserve the previous pleasant auto-gain at normal listening
            # levels, but only where the band owns a meaningful share of the
            # signal.  A broadband mix can fill all three bands; a 1 kHz tone
            # cannot masquerade as a bass hit merely through window leakage.
            presence = min(1.0, 3.5 * math.sqrt(band_power / analysis_power))
            value *= presence

            # Rise fast so kicks land on time, then leave a phosphor-like
            # tail rather than strobbing between terminal frames.
            previous = self._smooth[name]
            self._smooth[name] = (
                previous
                + (value - previous)
                * self._rate_alpha(
                    delta,
                    BASS_ATTACK_SECONDS if value > previous else BASS_RELEASE_SECONDS,
                )
            )
            out[name] = self._smooth[name]

        sub_power = float(np.sum(power[self._sub_bass_mask]))
        kick_power = float(np.sum(power[self._kick_mask]))
        out["sub_bass"] = min(1.0, math.sqrt(sub_power / analysis_power))
        out["kick"] = min(1.0, math.sqrt(kick_power / analysis_power))

        log_spectrum = np.log1p(spectrum)
        out["beat"] = self._update_onset(log_spectrum, now, delta)
        out["onset"] = out["beat"]

        # A compact log-frequency profile gives the renderer enough shape to
        # create distinct radial lobes instead of moving every pixel from the
        # same three broad values.
        edges = np.geomspace(30.0, 12_000.0, SPECTRUM_BINS + 1)
        buckets = np.zeros(SPECTRUM_BINS, dtype=np.float32)

        for index in range(SPECTRUM_BINS):
            mask = (freqs >= edges[index]) & (freqs < edges[index + 1])

            if mask.any():
                buckets[index] = float(np.mean(spectrum[mask]))

        buckets = np.log1p(buckets)
        peak = float(np.max(buckets))

        if peak > 1e-6:
            buckets /= peak

        gate = min(1.0, level * 3.0)
        buckets *= gate
        self._spectrum_smooth = np.maximum(
            buckets,
            self._spectrum_smooth * math.exp(-delta / BASS_RELEASE_SECONDS),
        )

        # Preserve the real waveform for the bright central oscilloscope.
        sample_indexes = np.linspace(
            0,
            WINDOW - 1,
            WAVEFORM_POINTS,
        ).astype(np.int32)
        waveform = samples[sample_indexes]
        wave_peak = max(0.025, float(np.max(np.abs(waveform))))
        waveform = np.clip(waveform / wave_peak, -1.0, 1.0)
        waveform *= min(1.0, level * 3.5)

        left_rms = float(np.sqrt(np.mean(stereo[:, 0] ** 2)))
        right_rms = float(np.sqrt(np.mean(stereo[:, 1] ** 2)))
        sum_rms = left_rms + right_rms
        difference = stereo[:, 0] - stereo[:, 1]
        combined = stereo[:, 0] + stereo[:, 1]
        width = float(np.sqrt(np.mean(difference ** 2)))
        centre = float(np.sqrt(np.mean(combined ** 2)))

        out["level"] = level
        out["stereo_width"] = min(1.0, width / (centre + 1e-6))
        out["pan"] = (
            max(-1.0, min(1.0, (right_rms - left_rms) / sum_rms))
            if sum_rms > 1e-6
            else 0.0
        )
        out["waveform"] = waveform.tolist()
        out["spectrum"] = self._spectrum_smooth.tolist()
        return out
