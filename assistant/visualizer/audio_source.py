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

import threading


SAMPLE_RATE = 44_100
BLOCK = 1024

# ~21 Hz per bin. Long enough for usable bass resolution, short enough
# to still feel immediate.
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

SILENT = {
    "bass": 0.0,
    "mid": 0.0,
    "treble": 0.0,
    "level": 0.0,
    "beat": 0.0,
    "stereo_width": 0.0,
    "pan": 0.0,
    "waveform": (),
    "spectrum": (),
}


class AudioSource:
    def __init__(self):
        self.error = None
        self.device_name = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._np = None
        self._buffer = None
        self._stereo_buffer = None
        self._window = None
        self._spectrum_smooth = None

        # Per-band decaying ceiling, so the display auto-gains to whatever
        # is playing instead of needing a volume control. Decay stops one
        # loud transient from flattening everything after it.
        self._ceiling = {name: 1e-6 for name in BANDS}
        self._smooth = {name: 0.0 for name in BANDS}
        self._prev_bass = 0.0
        self.beat = 0.0

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

        try:
            microphone = self._loopback_device(soundcard)
        except Exception as error:
            self.error = str(error)
            return False

        self.device_name = microphone.name
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(microphone,),
            daemon=True,
        )
        self._thread.start()

        # Surface a failure that happens immediately, rather than showing
        # a silent visualiser and letting it look like the music is quiet.
        self._thread.join(timeout=1.2)

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

    # -- analysis --------------------------------------------------------

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

        with self._lock:
            samples = self._buffer.copy()
            stereo = self._stereo_buffer.copy()

        if not np.any(samples):
            self.beat *= 0.7
            quiet = dict(SILENT)
            quiet["beat"] = self.beat
            return quiet

        spectrum = np.abs(np.fft.rfft(samples * self._window))
        freqs = np.fft.rfftfreq(WINDOW, 1.0 / SAMPLE_RATE)
        out = {}
        raw_level = float(np.sqrt(np.mean(samples ** 2)))
        level = min(1.0, raw_level * 6.0)

        for name, (low, high) in BANDS.items():
            mask = (freqs >= low) & (freqs < high)
            energy = float(np.mean(spectrum[mask])) if mask.any() else 0.0

            self._ceiling[name] = max(self._ceiling[name] * 0.999, energy, 1e-6)
            value = min(1.0, energy / self._ceiling[name])

            # Rise fast so hits land on time, then fall more gradually so
            # the field does not strobe between frames.
            previous = self._smooth[name]
            self._smooth[name] = (
                value if value > previous else previous * 0.82 + value * 0.18
            )
            out[name] = self._smooth[name]

        # A beat is bass *rising*, not merely bass being loud.
        rise = max(0.0, out["bass"] - self._prev_bass)
        self._prev_bass = out["bass"]
        self.beat = max(self.beat * 0.75, min(1.0, rise * 4.0))

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
            self._spectrum_smooth * 0.82,
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
        out["beat"] = self.beat
        out["stereo_width"] = min(1.0, width / (centre + 1e-6))
        out["pan"] = (
            max(-1.0, min(1.0, (right_rms - left_rms) / sum_rms))
            if sum_rms > 1e-6
            else 0.0
        )
        out["waveform"] = waveform.tolist()
        out["spectrum"] = self._spectrum_smooth.tolist()
        return out
