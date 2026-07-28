"""
Glossy turn-of-the-millennium audio-player visualizer.

This scene is intentionally a little more like a miniature media-player
window than a full-screen screensaver: a translucent display bezel, a
dual-trace oscilloscope, gel equalizer bars, and a spectrum-shaped orbital
ring all live in the same black-glass panel.  It uses only the shared
feature dictionary, so it reacts equally to loopback audio and local files.
"""

import math


CELL_W = 2
CELL_H = 4

_BRAILLE_WEIGHTS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

_BAYER = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


class Y2KPlayerVisualizer:
    """A black-glass player display with live meters and oscilloscope."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self.pan = 0.0
        self.stereo = 0.0
        self.pulse = 0.0
        self.flash = 0.0
        self._previous_beat = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

    def step(self, delta, features, _width, _height):
        """Advance the display with separate attack and release behaviour."""
        try:
            delta = max(0.0, float(delta))
        except (TypeError, ValueError):
            delta = 0.0

        features = features or {}
        bass = self._feature(features, "bass")
        mid = self._feature(features, "mid")
        treble = self._feature(features, "treble")
        beat = self._feature(features, "beat")
        stereo = self._feature(features, "stereo_width")
        pan = self._signed_feature(features, "pan")

        # Meters should snap to a kick, but their illuminated glass should
        # leave a short tail instead of flickering one frame at a time.
        self.bass = self._envelope(self.bass, bass, delta, 13.0, 3.4)
        self.mid = self._envelope(self.mid, mid, delta, 9.0, 4.2)
        self.treble = self._envelope(self.treble, treble, delta, 10.0, 5.2)
        self.stereo = self._envelope(self.stereo, stereo, delta, 8.0, 3.2)
        self.pan = self._signed_envelope(self.pan, pan, delta, 8.0, 4.0)

        self.time += delta * (0.45 + self.mid * 1.15 + self.bass * 0.26)
        self.pulse = max(beat, self.pulse * math.exp(-delta * 4.6))

        # A rising onset briefly blows out the chrome rim. Sustained bass
        # keeps the rings large, while only a true arrival creates a flash.
        if beat > 0.16 and beat > self._previous_beat + 0.045:
            self.flash = 1.0
        self.flash *= math.exp(-delta * 7.8)
        self._previous_beat = beat

    def render(self, width, height, features):
        """Return the conventional palette-coloured braille cell matrix."""
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        xx, yy, radius, angle = self._coordinates(pixel_w, pixel_h)

        features = features or {}
        level = self._feature(features, "level")
        spectrum = self._sequence(features.get("spectrum", ()), 48)
        waveform = self._sequence(features.get("waveform", ()), 128, signed=True)

        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)

        self._draw_glass_panel(intensity, highlight, xx, yy, level)
        self._draw_spectrum_orbit(
            intensity,
            highlight,
            radius,
            angle,
            spectrum,
            level,
        )
        self._draw_equalizer(
            intensity,
            highlight,
            spectrum,
            level,
        )
        self._draw_oscilloscope(
            intensity,
            highlight,
            waveform,
            level,
        )
        self._draw_stereo_markers(intensity, highlight, xx, yy, level)
        self._draw_sparkles(intensity, highlight, xx, yy)

        # On a beat, a narrow horizontal bloom unifies the distinct widgets
        # into the overexposed "glass display" look of old player skins.
        if self.flash > 0.01:
            centre_y = pixel_h * (0.485 + self.pan * 0.022)
            vertical = np.arange(pixel_h, dtype=np.float32)[:, None]
            flare = np.exp(
                -((vertical - centre_y) / (0.9 + self.flash * 3.8)) ** 2
            )
            intensity[:] = np.maximum(
                intensity,
                flare * self.flash * 0.52,
            )
            highlight |= flare > 0.76

        intensity = np.clip(intensity, 0.0, 1.0)
        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.145 + threshold * 0.66)
        dots |= highlight
        return self._to_cells(dots, intensity, highlight, width, height)

    def _draw_glass_panel(self, intensity, highlight, xx, yy, level):
        """Draw a rounded bevel, cloudy panel fill, and scanline texture."""
        np = self._np

        # A high-power superellipse avoids corners that read as a plain
        # terminal box, while still giving equalizer bars a strong bezel.
        panel = (np.abs(xx) / 1.13) ** 7 + (np.abs(yy) / 0.89) ** 7
        inside = panel < 1.0
        rim = np.exp(-((np.abs(panel - 1.0)) / 0.052) ** 2)
        outer_glow = np.exp(-((np.abs(panel - 1.0)) / 0.13) ** 2)
        intensity[:] = np.maximum(
            intensity,
            outer_glow * (0.045 + self.pulse * 0.11),
        )
        intensity[:] = np.maximum(
            intensity,
            rim * (0.32 + level * 0.17 + self.flash * 0.32),
        )

        # Airbrushed reflected light across the top left is the cue that
        # turns a line drawing into a glossy, translucent player panel.
        reflection = np.exp(
            -(
                ((xx + 0.32) / 0.66) ** 2
                + ((yy + 0.56) / 0.105) ** 2
            )
        )
        reflection += np.exp(
            -(
                ((xx - 0.60) / 0.19) ** 2
                + ((yy + 0.28) / 0.14) ** 2
            )
        ) * 0.42
        reflection *= inside
        intensity[:] = np.maximum(
            intensity,
            reflection * (0.30 + self.treble * 0.30),
        )
        highlight |= reflection > 0.58

        # The quiet internal fill lets the display remain recognizable in a
        # silent room without competing with music once audio arrives.
        scan = 0.5 + 0.5 * np.sin(yy * 112.0 + self.time * 3.2)
        scan *= inside * (0.018 + level * 0.037)
        intensity[:] = np.maximum(intensity, scan)

        # Small lower chrome edge and two artificial screw glints.
        lower_edge = np.exp(-((yy - 0.76) / 0.019) ** 2)
        lower_edge *= np.clip(1.0 - np.abs(xx) / 1.02, 0.0, 1.0)
        intensity[:] = np.maximum(
            intensity,
            lower_edge * (0.19 + self.bass * 0.16),
        )
        for glint_x in (-0.93, 0.93):
            glint = np.exp(
                -(((xx - glint_x) / 0.024) ** 2 + ((yy - 0.74) / 0.03) ** 2)
            )
            intensity[:] = np.maximum(intensity, glint * 0.55)
            highlight |= glint > 0.68

    def _draw_spectrum_orbit(
        self,
        intensity,
        highlight,
        radius,
        angle,
        spectrum,
        level,
    ):
        """Spectrum deforms a bright orbital ring around the oscilloscope."""
        np = self._np
        pixel_h, pixel_w = intensity.shape

        # The orbit moves laterally with pan. Slight vertical compression
        # makes it read as a physical chrome ring rather than a target.
        x, y, _, orbit_angle = self._coordinates(pixel_w, pixel_h)
        centre_x = self.pan * 0.15
        centre_y = 0.025
        orbit_radius = np.sqrt(
            ((x - centre_x) * 0.83) ** 2
            + ((y - centre_y) * 1.14) ** 2
        )
        orbit_angle = np.arctan2((y - centre_y) * 1.14, (x - centre_x) * 0.83)

        positions = (
            (orbit_angle + math.pi) / (2.0 * math.pi) * (spectrum.size - 1)
        )
        energy = np.interp(
            positions.ravel(),
            np.arange(spectrum.size),
            spectrum,
        ).reshape(orbit_radius.shape)

        # Low frequencies visibly push the ring outward. The individual
        # spectrum bands add the serrated equalizer crown around it.
        target = (
            0.258
            + self.bass * 0.080
            + self.pulse * 0.045
            + energy * (0.055 + self.treble * 0.030)
            + np.sin(orbit_angle * 4.0 - self.time * 2.4) * 0.008
        )
        distance = np.abs(orbit_radius - target)
        glow = np.exp(-((distance / (0.080 + self.pulse * 0.022)) ** 2))
        shell = np.exp(-((distance / (0.016 + self.treble * 0.010)) ** 2))
        intensity[:] = np.maximum(
            intensity,
            glow * (0.10 + level * 0.17 + energy * 0.14),
        )
        intensity[:] = np.maximum(
            intensity,
            shell * (0.42 + energy * 0.37 + self.flash * 0.18),
        )
        highlight |= shell > (0.88 - self.flash * 0.20)

        # A second, counter-rotating tilted ring makes the center feel like
        # a chrome 3D widget, with stereo width opening its ellipse.
        tilt = 0.48 + self.stereo * 0.32
        cosine = math.cos(tilt)
        sine = math.sin(tilt)
        rotated_x = (x - centre_x) * cosine - (y - centre_y) * sine
        rotated_y = (x - centre_x) * sine + (y - centre_y) * cosine
        ellipse = np.sqrt((rotated_x / 0.42) ** 2 + (rotated_y / 0.13) ** 2)
        secondary_target = 1.0 + self.mid * 0.06 + self.pulse * 0.04
        secondary = np.exp(-((np.abs(ellipse - secondary_target) / 0.042) ** 2))
        intensity[:] = np.maximum(
            intensity,
            secondary * (0.17 + self.stereo * 0.31 + level * 0.10),
        )

    def _draw_equalizer(self, intensity, highlight, spectrum, level):
        """Fill the bottom of the display with capped, glassy spectrum bars."""
        np = self._np
        pixel_h, pixel_w = intensity.shape
        bars = max(4, min(34, pixel_w // 4))
        baseline = min(pixel_h - 1, max(1, int(pixel_h * 0.825)))
        usable = max(1, baseline - max(0, int(pixel_h * 0.57)))
        spacing = pixel_w / bars
        spectrum_positions = np.linspace(0, spectrum.size - 1, bars)
        energies = np.interp(
            spectrum_positions,
            np.arange(spectrum.size),
            spectrum,
        )

        for index, raw_energy in enumerate(energies):
            energy = self._clamp(raw_energy)
            centre = int((index + 0.5) * spacing)
            half = max(1, int(spacing * 0.27))
            left = max(0, centre - half)
            right = min(pixel_w, centre + half + 1)
            if left >= right:
                continue

            # A slight pan tilt causes the two visible ends of the meter to
            # feel like left and right channels rather than a static chart.
            balance = (index / max(1, bars - 1) - 0.5) * self.pan * 0.18
            height_fraction = (
                0.08
                + energy * 0.73
                + self.bass * (0.09 if index < bars * 0.34 else 0.025)
                + self.pulse * 0.055
                + balance
            )
            bar_height = max(1, int(usable * self._clamp(height_fraction)))
            top = max(0, baseline - bar_height)
            body = 0.17 + energy * 0.42 + level * 0.10
            intensity[top:baseline + 1, left:right] = np.maximum(
                intensity[top:baseline + 1, left:right],
                body,
            )

            # Bright left edge, dimmer right edge, and an oval cap produce
            # the translucent 'gel column' treatment of classic skins.
            intensity[top:baseline + 1, left:left + 1] = np.maximum(
                intensity[top:baseline + 1, left:left + 1],
                0.47 + energy * 0.31,
            )
            intensity[top:baseline + 1, max(left, right - 1):right] = np.maximum(
                intensity[top:baseline + 1, max(left, right - 1):right],
                0.31 + energy * 0.23,
            )
            cap_left = max(0, left - 1)
            cap_right = min(pixel_w, right + 1)
            intensity[max(0, top - 1):min(pixel_h, top + 2), cap_left:cap_right] = (
                np.maximum(
                    intensity[
                        max(0, top - 1):min(pixel_h, top + 2),
                        cap_left:cap_right,
                    ],
                    0.39 + energy * 0.49,
                )
            )
            if energy > 0.54 or (index < bars * 0.18 and self.bass > 0.64):
                highlight[
                    max(0, top - 1):min(pixel_h, top + 1),
                    max(0, centre - 1):min(pixel_w, centre + 1),
                ] = True

            # Segment gaps stop a bar becoming a generic skyline at small
            # terminal sizes and retain an unmistakable player-meter look.
            segment = max(3, pixel_h // 15)
            for row in range(top + segment, baseline, segment + 2):
                intensity[row:row + 1, left:right] *= 0.34

    def _draw_oscilloscope(self, intensity, highlight, waveform, level):
        """Draw a real central trace and a stereo-separated echo trace."""
        np = self._np
        pixel_h, pixel_w = intensity.shape
        if waveform.size < 2:
            waveform = np.sin(
                np.linspace(0.0, math.pi * 4.0, 64, dtype=np.float32)
                + self.time * 2.0,
            ) * 0.03

        left_margin = min(2, max(0, pixel_w - 1))
        right_edge = max(left_margin, pixel_w - 1 - left_margin)
        xs = np.linspace(left_margin, right_edge, waveform.size).astype(
            np.int32,
        )
        centre = pixel_h * (0.47 + self.pan * 0.024)
        amplitude = pixel_h * (0.035 + level * 0.105 + self.stereo * 0.030)
        separation = pixel_h * (0.012 + self.stereo * 0.060)
        trace_a = np.clip(
            np.rint(centre - waveform * amplitude - separation),
            0,
            pixel_h - 1,
        ).astype(np.int32)

        # There is only one captured waveform, so the second channel is a
        # short, deliberately subtle delay. It widens exactly with real
        # stereo content and never invents a large fake signal in mono.
        delay = max(1, int(2 + self.stereo * 7))
        echo = np.roll(waveform, delay) * (0.78 + self.stereo * 0.18)
        trace_b = np.clip(
            np.rint(centre - echo * amplitude + separation),
            0,
            pixel_h - 1,
        ).astype(np.int32)

        for index in range(len(xs) - 1):
            self._line(
                intensity,
                xs[index],
                trace_b[index],
                xs[index + 1],
                trace_b[index + 1],
                0.48 + self.stereo * 0.20,
            )
            self._line(
                intensity,
                xs[index],
                trace_a[index],
                xs[index + 1],
                trace_a[index + 1],
                1.0,
            )
            self._line(
                highlight,
                xs[index],
                trace_a[index],
                xs[index + 1],
                trace_a[index + 1],
                True,
            )

        # Low-frequency knock causes a restrained phosphor bloom around the
        # real trace instead of faking a bigger waveform shape.
        bloom = min(0.78, 0.24 + self.bass * 0.42 + self.pulse * 0.24)
        for offset in (-1, 1):
            shifted = np.clip(trace_a + offset, 0, pixel_h - 1)
            intensity[shifted, xs] = np.maximum(intensity[shifted, xs], bloom)

    def _draw_stereo_markers(self, intensity, highlight, xx, yy, level):
        """Add small pan-biased meter pips at either side of the trace."""
        np = self._np
        centre_y = 0.02 + self.pan * 0.020
        for direction in (-1.0, 1.0):
            side = -0.74 if direction < 0 else 0.74
            # Positive pan brightens the right meter and vice versa.
            channel = self._clamp(0.52 + direction * self.pan * 0.48)
            x_distance = np.abs(xx - side)
            y_distance = np.abs(yy - centre_y)
            body = np.exp(-((x_distance / 0.028) ** 2))
            body *= np.clip((0.21 - y_distance) / 0.018, 0.0, 1.0)
            intensity[:] = np.maximum(
                intensity,
                body * (0.16 + channel * (0.30 + level * 0.20)),
            )
            highlight |= body > 0.90

        # The width readout is a thin expanding halo, not a text label, so
        # it works at every terminal size and stays inside the scene style.
        width_line = np.exp(-((np.abs(yy - 0.47) - self.stereo * 0.12) / 0.014) ** 2)
        width_line *= np.clip((np.abs(xx) - 0.47) / 0.10, 0.0, 1.0)
        intensity[:] = np.maximum(
            intensity,
            width_line * (0.10 + self.stereo * 0.26),
        )

    def _draw_sparkles(self, intensity, highlight, xx, yy):
        """Keep a few deterministic chrome glints in the quiet border."""
        np = self._np
        shimmer = (
            np.sin(xx * 91.0 + yy * 47.0 + self.time * 2.8)
            * np.sin(xx * 29.0 - yy * 103.0 - self.time * 1.7)
        )
        border = (np.abs(xx) > 0.91) | (np.abs(yy) > 0.70)
        stars = border & (shimmer > 0.992 - self.treble * 0.020)
        intensity[stars] = np.maximum(
            intensity[stars],
            0.36 + self.treble * 0.42,
        )
        highlight |= stars & (shimmer > 0.998 - self.flash * 0.015)

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)
        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.22, 1.22, pixel_w, dtype=np.float32)
        y = np.linspace(-0.96, 0.96, pixel_h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        self._grid = (
            xx,
            yy,
            np.sqrt(xx ** 2 + yy ** 2),
            np.arctan2(yy, xx),
        )
        self._grid_key = key
        return self._grid

    def _sequence(self, values, fallback_size, signed=False):
        """Coerce an optional shared analyser sequence into safe float data."""
        np = self._np
        try:
            sequence = np.asarray(values, dtype=np.float32).reshape(-1)
        except (TypeError, ValueError):
            sequence = np.empty(0, dtype=np.float32)
        if sequence.size < 2:
            return np.zeros(fallback_size, dtype=np.float32)
        sequence = np.nan_to_num(sequence, nan=0.0, posinf=1.0, neginf=-1.0)
        if signed:
            return np.clip(sequence, -1.0, 1.0)
        return np.clip(sequence, 0.0, 1.0)

    def _line(self, target, x0, y0, x1, y1, value):
        """Draw a clipped line into a fine-pixel field."""
        np = self._np
        height, width = target.shape
        count = int(max(abs(x1 - x0), abs(y1 - y0))) + 2
        xs = np.linspace(x0, x1, count).astype(np.int32)
        ys = np.linspace(y0, y1, count).astype(np.int32)
        keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
        if not np.any(keep):
            return
        if target.dtype == bool:
            target[ys[keep], xs[keep]] = bool(value)
        else:
            target[ys[keep], xs[keep]] = np.maximum(
                target[ys[keep], xs[keep]],
                value,
            )

    def _to_cells(self, dots, intensity, highlight, width, height):
        """Pack fine pixels into the shared coloured braille-cell format."""
        np = self._np
        grid = dots.reshape(height, CELL_H, width, CELL_W)
        weights = np.asarray(_BRAILLE_WEIGHTS, dtype=np.uint16)
        bits = (grid * weights[None, :, None, :]).sum(axis=(1, 3))
        strength = intensity.reshape(height, CELL_H, width, CELL_W).max(axis=(1, 3))
        bright = highlight.reshape(height, CELL_H, width, CELL_W).any(axis=(1, 3))

        palette = self.palette or ("",)
        top = len(palette) - 1
        rows = []
        for y in range(height):
            row = []
            for x in range(width):
                packed = int(bits[y, x])
                if not packed:
                    row.append(None)
                    continue
                if top <= 0 or bright[y, x]:
                    colour = top
                else:
                    colour = min(
                        top - 1,
                        max(0, int(float(strength[y, x]) * top)),
                    )
                row.append((chr(0x2800 + packed), palette[colour]))
            rows.append(row)
        return rows

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _feature(cls, features, name):
        try:
            value = features.get(name, 0.0)
        except AttributeError:
            value = 0.0
        return cls._clamp(value)

    @classmethod
    def _signed_feature(cls, features, name):
        try:
            value = float(features.get(name, 0.0))
        except (AttributeError, TypeError, ValueError):
            value = 0.0
        return max(-1.0, min(1.0, value))

    @staticmethod
    def _envelope(current, target, delta, attack, release):
        speed = attack if target >= current else release
        response = min(1.0, delta * speed)
        return current + (target - current) * response

    @staticmethod
    def _signed_envelope(current, target, delta, attack, release):
        speed = attack if abs(target) >= abs(current) else release
        response = min(1.0, delta * speed)
        return current + (target - current) * response
