"""Sable's own scene: a preservation field read by an anchor trace.

Every other scene borrows a shape from somewhere -- a tunnel, a lattice, rain.
This one borrows from the two things this project actually built, and the
whole design rule is that each element means what it means elsewhere in the
program rather than merely looking like it.

  machinesoul   The field. Ordered four-coordinate vectors written into
                pixels in storage order, scrolling upward because that is the
                direction a capsule fills. Density follows the spectrum, so
                the music is what is being preserved.

  machinespirit The lanes. Horizontal rows that light when a band crosses,
                each anchor holding one lane for the life of the scene --
                the same rule the vector panel follows, and for the same
                reason: a row lighting across time is one concept persisting,
                and a row that moves is a chart nobody can read.

  the beam      The reader, travelling left to right, slowing where the
                spectrum turns. Lifted from the APNG trajectory beam, where
                frame duration is proportional to how far the meaning moved.

  the gate      On a beat the field is verified. It resolves bright, or it
                refuses and blanks a band -- reversible 1:1 or refusal, with
                no third outcome. A visualizer cannot verify anything, so the
                pulse is honest about being a rhythm and not a checksum.

Palette-driven like every other scene, so it inherits the rotation rather
than hardcoding Sable's colours over the operator's choice.
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

# Anchor lanes. Enough to read as a dictionary, few enough that each keeps a
# legible band of its own on a short terminal.
_LANES = 7

# A lane holds its light this long after the band that lit it falls away, so
# the trace reads as persistence rather than flicker.
_LANE_DECAY = 3.1


class SableFieldVisualizer:
    """The preservation field, its anchor lanes, and the beam that reads it."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.slow = 0.0
        # How far the field has filled. Integrated from a bass-driven rate,
        # so it only ever moves forward.
        self.scroll = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self.pulse = 0.0
        self.gate = 0.0
        self.refused = 0.0
        # The beam's position along the field, and how fast it is reading.
        self.beam = 0.0
        self.beam_rate = 0.34
        self.lanes = [0.0] * _LANES
        self._previous_beat = 0.0
        self._previous_spectrum = None
        self._np = None
        self._field = None

    # ------------------------------------------------------------------
    # STATE
    # ------------------------------------------------------------------

    def step(self, dt, features, _width, _height):
        try:
            dt = max(0.0, min(0.25, float(dt)))
        except (TypeError, ValueError):
            dt = 0.0

        features = features or {}
        response = 1.0 - math.exp(-dt * 8.0)
        bass = self._feature(features, "bass")
        mid = self._feature(features, "mid")
        treble = self._feature(features, "treble")
        beat = self._feature(features, "beat")

        # Fast up, slow down. One symmetric coefficient made every band arrive
        # late and leave early: a hit was still climbing when the transient
        # had already passed, so the field read as following the music rather
        # than being struck by it. Attack is nearly instant now; release keeps
        # the old pace, which is what stops the field strobing and lets it
        # breathe back down between hits.
        attack = 1.0 - math.exp(-dt * 26.0)
        release = 1.0 - math.exp(-dt * 7.0)

        self.bass += (bass - self.bass) * (
            attack if bass > self.bass else release)
        self.mid += (mid - self.mid) * (
            attack if mid > self.mid else release)
        self.treble += (treble - self.treble) * (
            attack if treble > self.treble else release)

        # Wall-clock, deliberately unscaled by audio. A reference that speeds
        # up with the music is not a reference -- visualizer/anchor.py makes
        # the same argument, and the lanes here are the reference.
        self.slow += dt
        self.time += dt * (0.5 + self.mid * 1.5)

        # Integrated, not `slow * rate`. Multiplying elapsed time by a rate
        # that changes means the whole field jumps whenever bass moves --
        # sixty seconds in, a bass swell displaced it by tens of rows at once,
        # which read as a glitch rather than as speed. Accumulating the rate
        # makes bass drive how fast the capsule fills, which is the thing it
        # was always supposed to mean.
        # Squared for the same reason the field density is: the lifted floor
        # would otherwise keep the capsule filling at half speed through a
        # silent passage.
        self.scroll += dt * (0.26 + (self.bass ** 2) * 2.6)

        # The beam slows where the spectrum turns, which is the rule the APNG
        # beam uses: frame duration in proportion to distance moved. A steady
        # passage reads fast; a change is worth dwelling on.
        turn = self._spectral_turn(features)
        self.beam_rate += ((0.16 + 0.72 * (1.0 - turn)) - self.beam_rate) * response
        self.beam = (self.beam + dt * self.beam_rate) % 1.0

        self.pulse = max(beat, self.pulse * math.exp(-dt * 4.4))

        if beat > 0.14 and beat > self._previous_beat + 0.045:
            self.gate = 1.0
            # Refusal is rarer than verification and must look like a
            # decision, not a dropout. Bound to bass so it lands on weight.
            self.refused = 1.0 if self.bass > 0.62 else 0.0
        self.gate *= math.exp(-dt * 5.6)
        self.refused *= math.exp(-dt * 6.8)
        self._previous_beat = beat

        self._step_lanes(dt, features)

    def _step_lanes(self, dt, features):
        """Light each lane from its own slice of the spectrum, then decay."""
        spectrum = self._spectrum_list(features)
        decay = math.exp(-dt * _LANE_DECAY)

        for index in range(_LANES):
            if spectrum:
                low = int(index * len(spectrum) / _LANES)
                high = max(low + 1, int((index + 1) * len(spectrum) / _LANES))
                support = max(spectrum[low:high])
            else:
                support = 0.0
            # Rise immediately, fall slowly: a concept appears at a token and
            # then fades, rather than strobing with the frame rate.
            self.lanes[index] = max(support, self.lanes[index] * decay)

    def _spectral_turn(self, features):
        """How much the spectrum moved since the last frame, 0..1."""
        spectrum = self._spectrum_list(features)
        if not spectrum:
            return 0.0
        previous, self._previous_spectrum = self._previous_spectrum, spectrum
        if not previous or len(previous) != len(spectrum):
            return 0.0
        moved = sum(abs(a - b) for a, b in zip(spectrum, previous))
        return max(0.0, min(1.0, moved / len(spectrum) * 4.0))

    # ------------------------------------------------------------------
    # RENDER
    # ------------------------------------------------------------------

    def render(self, width, height, features):
        if self._np is None:
            import numpy as np
            self._np = np
            self._rng = np.random.default_rng(0x5AB1E)

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H

        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)

        ys = np.arange(pixel_h, dtype=np.float32)[:, None]
        xs = np.arange(pixel_w, dtype=np.float32)[None, :]
        u = xs / max(1.0, pixel_w - 1)
        v = ys / max(1.0, pixel_h - 1)

        self._draw_field(intensity, u, v, pixel_h, pixel_w)
        self._draw_lanes(intensity, highlight, u, v, pixel_h)
        self._draw_beam(intensity, highlight, u, v)
        self._draw_gate(intensity, highlight, v)

        intensity = np.clip(intensity, 0.0, 1.0)
        dots = intensity > 0.30
        return self._pack(dots, intensity, highlight, width, height)

    def _draw_field(self, intensity, u, v, pixel_h, pixel_w):
        """machinesoul: ordered vectors as pixels, scrolling in written order.

        Four coordinates per cell, so the texture is built from a four-phase
        interference rather than one wave -- the field is RGBA, and looking
        like a single channel would misrepresent what a capsule holds.
        """
        np = self._np
        rows = v * 26.0 + self.scroll * 6.0
        cols = u * 34.0

        field = np.zeros_like(intensity)
        for phase, weight in ((0.0, 0.34), (1.7, 0.28), (3.1, 0.22), (4.6, 0.16)):
            field += weight * np.sin(rows * 1.7 + phase + np.cos(cols * 0.9 + phase))

        # Gamma before scale, not after. A braille cell lights if any of its
        # eight dots clears the threshold, so a field whose mean sits near
        # that threshold lights almost every cell and reads as fog. Pushing
        # the mid-tones down keeps the peaks and leaves the lanes and the
        # beam somewhere to be read against.
        # Base kept low on purpose: quiet passages must actually go quiet.
        # At 0.30 the field cleared the dot threshold on its own and a
        # silent track looked much like a loud one.
        #
        # Expanded here, not merely amplified upstream. reactivity.py lifts
        # quiet detail so it is visible at all, which means a near-silent
        # passage still arrives in this method around 0.45 -- so raising the
        # profile gains alone raised the floor exactly as much as the ceiling
        # and bought a quiet-to-loud contrast of about two to one. Measured,
        # not assumed.
        #
        # Squaring pushes the quiet back down without touching the peaks, so
        # the distance between a verse and a chorus is roughly four to one.
        # That is what "more reactive" actually means for this scene: not a
        # brighter average, a wider gap. Above 1.0 the field saturates rather
        # than brightening further, which is fine -- a chorus is allowed to
        # look like the field is full.
        density = 0.06 + 0.86 * (self.mid ** 2) + 0.46 * (self.treble ** 2)
        shaped = np.clip(field * 0.5 + 0.5, 0.0, 1.0) ** 3.0
        intensity += shaped * density

    def _draw_lanes(self, intensity, highlight, u, v, pixel_h):
        """machinespirit: one anchor, one lane, held for the scene's life."""
        np = self._np
        for index, support in enumerate(self.lanes):
            if support <= 0.02:
                continue
            centre = (index + 0.5) / _LANES
            band = np.exp(-((v - centre) ** 2) / (2.0 * (0.016 ** 2)))

            # Broken along its length rather than ruled across it. A lane in
            # the vector panel lights at token positions, not continuously,
            # and a solid bar would claim a concept was present at every
            # moment instead of at the ones that scored. The per-lane phase
            # keeps the marks from lining up into a grid.
            marks = np.sin(u * (46.0 + index * 7.0) - self.time * 1.6
                           + index * 2.3)
            marks = np.clip(marks, 0.0, 1.0) ** 1.6

            # Support is brightness, exactly as it is in the vector panel:
            # position says which concept, never how strongly it scored.
            intensity += band * marks * (0.34 + 0.66 * support)
            if support > 0.55:
                highlight |= (band * marks) > 0.55

    def _draw_beam(self, intensity, highlight, u, v):
        """The reader, dwelling where the spectrum turns."""
        np = self._np
        head = abs(u - self.beam)
        head = np.minimum(head, 1.0 - head)          # wraps, like the loop
        glow = np.exp(-(head ** 2) / (2.0 * (0.012 ** 2)))
        intensity += glow * (0.55 + 0.45 * self.pulse)
        highlight |= glow > 0.62

        # A short trail behind it, so direction is readable at a glance.
        behind = (self.beam - u) % 1.0
        trail = np.exp(-behind / 0.07) * (behind < 0.25)
        intensity += trail * 0.22

    def _draw_gate(self, intensity, highlight, v):
        """Verified, or refused. There is no third outcome."""
        np = self._np
        if self.gate <= 0.02:
            return

        sweep = 1.0 - abs(v - (1.0 - self.gate))
        line = np.exp(-((sweep - 1.0) ** 2) / (2.0 * (0.03 ** 2)))

        if self.refused > 0.02:
            # Refusal keeps nothing: the band is cleared rather than dimmed,
            # because a partial capsule is the one thing machinesoul never
            # leaves behind.
            intensity *= 1.0 - np.clip(line * self.refused, 0.0, 1.0)
        else:
            intensity += line * self.gate * 0.85
            highlight |= line > 0.70

    def _pack(self, dots, intensity, highlight, width, height):
        """Into the shared coloured braille-cell format the canvas expects."""
        np = self._np
        grid = dots.reshape(height, CELL_H, width, CELL_W)
        weights = np.asarray(_BRAILLE_WEIGHTS, dtype=np.uint16)
        bits = (grid * weights[None, :, None, :]).sum(axis=(1, 3))
        strength = intensity.reshape(height, CELL_H, width, CELL_W).max(axis=(1, 3))
        bright = highlight.reshape(height, CELL_H, width, CELL_W).any(axis=(1, 3))

        palette = self.palette or ("",)
        top = len(palette) - 1
        rows = []
        for row_index in range(height):
            row = []
            for col_index in range(width):
                packed = int(bits[row_index, col_index])
                if not packed:
                    row.append(None)
                    continue
                if top <= 0 or bright[row_index, col_index]:
                    colour = top
                else:
                    colour = min(
                        top - 1,
                        max(0, int(float(strength[row_index, col_index]) * top)),
                    )
                row.append((chr(0x2800 + packed), palette[colour]))
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    # FEATURES
    # ------------------------------------------------------------------

    def _spectrum_list(self, features):
        try:
            spectrum = features.get("spectrum", ())
        except AttributeError:
            return []
        try:
            return [max(0.0, min(1.0, float(value))) for value in spectrum]
        except (TypeError, ValueError):
            return []

    @staticmethod
    def _feature(features, name):
        try:
            value = features.get(name, 0.0)
        except AttributeError:
            return 0.0
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
