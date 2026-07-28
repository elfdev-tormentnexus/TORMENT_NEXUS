"""
Acid-green fractured lattice for the terminal music visualizer.

This is an original terminal scene built from the supplied reference video's
visual language rather than its footage: deep black negative space, an
overgrown triangular wire mesh, jagged horizons, diagonal scans, and rare
overexposed fracture bursts.  It deliberately avoids a Matrix-style code
curtain; the image should feel skeletal, angular, and harshly clipped.
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


class AcidLatticeVisualizer:
    """Angular wire mesh, moving void, and beat-driven fracture flashes."""

    def __init__(self, palette):
        self.palette = tuple(palette)
        self.time = 0.0
        self.bass = 0.0
        self.mid = 0.0
        self.treble = 0.0
        self.stereo = 0.0
        self.pan = 0.0
        self.pulse = 0.0
        self.fracture = 0.0
        # Wall-clock seconds, deliberately not scaled by audio. A reference
        # that speeds up with the music is not a reference.
        self.slow = 0.0
        self._previous_beat = 0.0
        self._np = None
        self._grid_key = None
        self._grid = None

    def step(self, delta, features, _width, _height):
        """Advance the drifting mesh and recognize a fresh musical onset."""
        try:
            delta = max(0.0, min(0.25, float(delta)))
        except (TypeError, ValueError):
            delta = 0.0

        bass = self._feature(features, "bass")
        mid = self._feature(features, "mid")
        treble = self._feature(features, "treble")
        beat = self._feature(features, "beat")
        stereo = self._feature(features, "stereo_width")
        pan = self._signed_feature(features, "pan")

        # The lattice has enough inertia to feel like a physical field,
        # while a low drum arrives quickly enough to visibly pull its black
        # horizon upwards.
        self.bass = self._envelope(self.bass, bass, delta, 13.0, 3.5)
        self.mid = self._envelope(self.mid, mid, delta, 9.0, 4.0)
        self.treble = self._envelope(self.treble, treble, delta, 11.0, 4.8)
        self.stereo = self._envelope(self.stereo, stereo, delta, 8.0, 3.6)
        self.pan = self._signed_envelope(self.pan, pan, delta, 9.0, 4.0)
        self.time += delta * (0.42 + self.mid * 1.18 + self.treble * 0.42)
        self.slow += delta
        self.pulse = max(beat, self.pulse * math.exp(-delta * 4.5))

        # A sustained loud passage should keep the mesh energized, but only
        # a rising onset gets the deliberately rare hard-cut starburst.
        if beat > 0.16 and beat > self._previous_beat + 0.045:
            self.fracture = 1.0
        self.fracture *= math.exp(-delta * 6.8)
        self._previous_beat = beat

    def render(self, width, height, features):
        """Return a palette-coloured braille image for the terminal canvas."""
        if self._np is None:
            import numpy as np
            self._np = np

        np = self._np
        width = max(1, int(width))
        height = max(1, int(height))
        pixel_w = width * CELL_W
        pixel_h = height * CELL_H
        xx, yy = self._coordinates(pixel_w, pixel_h)

        level = self._feature(features, "level")
        spectrum = self._sequence(self._value(features, "spectrum", ()), 48)
        intensity = np.zeros((pixel_h, pixel_w), dtype=np.float32)
        highlight = np.zeros((pixel_h, pixel_w), dtype=bool)

        horizon = self._horizon(xx, spectrum)
        mesh_mask = yy < horizon
        self._draw_slow_anchor(intensity, xx, yy)
        self._draw_upper_lattice(
            intensity,
            highlight,
            xx,
            yy,
            horizon,
            mesh_mask,
            spectrum,
            level,
        )
        self._draw_horizon(intensity, highlight, xx, yy, horizon, level)
        self._draw_foreground_shards(
            intensity,
            highlight,
            xx,
            yy,
            horizon,
            spectrum,
            level,
        )
        self._draw_scans(intensity, highlight, xx, yy, horizon, mesh_mask)
        self._draw_fracture_burst(intensity, highlight, xx, yy, horizon)

        intensity = np.clip(intensity, 0.0, 1.0)
        bayer = np.asarray(_BAYER, dtype=np.float32) / 15.0
        threshold = np.tile(
            bayer,
            ((pixel_h + 3) // 4, (pixel_w + 3) // 4),
        )[:pixel_h, :pixel_w]
        dots = intensity > (0.17 + threshold * 0.64)
        dots |= highlight
        return self._to_cells(dots, intensity, highlight, width, height)

    def _horizon(self, xx, spectrum):
        """Return a bass-pulled sawtooth boundary between mesh and void."""
        np = self._np
        positions = np.clip(
            (xx[0] + 1.42) / 2.84 * (spectrum.size - 1),
            0.0,
            spectrum.size - 1,
        )
        band = np.interp(
            positions,
            np.arange(spectrum.size, dtype=np.float32),
            spectrum,
        )

        # Two disagreeing triangular waves yield a jagged cut without
        # turning the horizon into a clean equalizer silhouette.
        saw_a = (2.0 / math.pi) * np.arcsin(
            np.sin(xx[0] * 7.3 + self.time * 0.72 + self.pan * 0.55)
        )
        saw_b = (2.0 / math.pi) * np.arcsin(
            np.sin(xx[0] * 16.7 - self.time * 1.13)
        )
        base = 0.11 - self.bass * 0.29 - self.pulse * 0.075
        horizon = base + saw_a * 0.052 + saw_b * 0.018 - band * 0.105
        return np.clip(horizon, -0.52, 0.42).astype(np.float32)

    def _draw_slow_anchor(self, intensity, xx, yy):
        """
        A slow, frame-wide strata the fast lattice is read against.

        Two problems, one element. The scene had nothing to measure its
        motion by: every layer moved at audio speed, so a fast passage and
        a slow one looked equally busy and neither read as fast. And the
        lower left was empty by construction -- the mesh is masked above
        the horizon and the shards are cut away to the right, so a whole
        quadrant of the frame was unreachable by anything that drew.

        These strata cross the entire frame, ignore the horizon, and drift
        on wall-clock time alone: about one band every twelve seconds
        regardless of what the music does. Dim enough to sit under the
        lattice, present enough that the void has a floor.
        """
        np = self._np
        field = (
            yy * 2.15
            + np.sin(xx * 0.85 - self.slow * 0.045) * 0.34
            + np.sin(xx * 1.9 + self.slow * 0.028) * 0.11
            - self.slow * 0.085
        )
        strata = self._triangle_lines(field)

        # The dither ramp runs 0.17 to 0.81, so brightness here is really a
        # coverage control: 0.235 cleared the floor on about a tenth of the
        # subpixels and the strata arrived as scattered dots rather than as
        # bands. This lands near half coverage -- unmistakably a line, still
        # visibly beneath the lattice cores above it.
        intensity[:] = np.maximum(
            intensity,
            strata * (0.475 + self.mid * 0.085),
        )

    def _draw_upper_lattice(
        self,
        intensity,
        highlight,
        xx,
        yy,
        horizon,
        mesh_mask,
        spectrum,
        level,
    ):
        """Draw two warped, triangular wire-mesh layers above the void."""
        np = self._np

        spectrum_position = np.clip(
            (xx + 1.42) / 2.84 * (spectrum.size - 1),
            0.0,
            spectrum.size - 1,
        )
        band = np.interp(
            spectrum_position.ravel(),
            np.arange(spectrum.size, dtype=np.float32),
            spectrum,
        ).reshape(xx.shape)

        # A quiet, nonuniform drift keeps the mesh hand-drawn rather than
        # reading as a perfectly rendered math grid. Stereo widens it and
        # pan shifts the two layers in opposite directions.
        warp_x = (
            xx
            + np.sin(yy * 5.6 + self.time * 0.82) * (0.048 + self.mid * 0.040)
            + np.sin(xx * 11.0 - yy * 2.7 - self.time * 0.43) * 0.020
            + self.pan * 0.075
        )
        warp_y = (
            yy
            + np.sin(xx * 4.2 - self.time * 0.63) * (0.036 + self.stereo * 0.036)
            + band * (0.028 + self.mid * 0.035)
        )
        # Three orientations at the old 5.1-12.0 put a line every three
        # cells. Braille resolves a line and it resolves a gap, but at that
        # spacing the three families interleave into texture and the eye
        # reads noise instead of a mesh -- which is the other half of why
        # this scene looked wrong. Opened out to roughly one line every ten
        # cells, so a triangle is a shape rather than a shimmer. The audio
        # range is kept proportionally wide: growing the field is still the
        # scene's main response to mids and treble.
        density = 3.40 + self.mid * 1.70 + self.treble * 1.30
        phase = self.time * (0.85 + self.mid * 0.62)

        layer_a = self._triangle_lines(warp_x * density + phase)
        layer_b = self._triangle_lines(
            (warp_x * 0.50 + warp_y * 0.866) * density * 1.03 - phase * 0.78
        )
        layer_c = self._triangle_lines(
            (warp_x * 0.50 - warp_y * 0.866) * density * 0.95 + phase * 0.63
        )
        mesh = np.maximum(layer_a, np.maximum(layer_b, layer_c))

        # A more distant offset mesh generates the dense nested web seen in
        # the reference. It remains dim so the black negative space wins.
        far_x = warp_x * 1.13 - self.pan * 0.15
        far_y = warp_y * 1.09 + 0.10
        far_density = density * (0.60 + self.treble * 0.16)
        far = np.maximum(
            self._triangle_lines(far_x * far_density - phase * 0.51),
            self._triangle_lines(
                (far_x * 0.50 + far_y * 0.866) * far_density + phase * 0.36
            ),
        )

        # Brighter at an irregular subset of intersections. The sparse
        # nodes make a wire mesh look built from triangles rather than from
        # generic diagonal hatching.
        crossings = np.minimum(layer_a, np.maximum(layer_b, layer_c))
        node_field = np.sin(warp_x * 27.0 + warp_y * 19.0 + self.time * 1.7)
        nodes = crossings * (node_field > 0.76)
        fade = np.clip((horizon[None, :] - yy + 0.05) / 0.36, 0.22, 1.0)
        strength = (
            mesh * (0.27 + level * 0.21 + self.mid * 0.18 + band * 0.16)
            + far * (0.070 + self.treble * 0.095)
        ) * mesh_mask * fade
        intensity[:] = np.maximum(intensity, strength)
        node_strength = nodes * mesh_mask * (0.38 + self.treble * 0.25)
        intensity[:] = np.maximum(intensity, node_strength)

    def _draw_horizon(self, intensity, highlight, xx, yy, horizon, level):
        """Give the void a bright, broken rim instead of a flat boundary."""
        np = self._np
        distance = np.abs(yy - horizon[None, :])
        scale = max(0.014, 2.0 / max(yy.shape[0] - 1, 1) * 1.25)
        rim = np.exp(-((distance / scale) ** 2))
        fragments = (
            np.sin(xx * 31.0 + self.time * 4.4)
            * np.sin(xx * 8.7 - self.time * 1.1)
        )
        broken = np.where(fragments > -0.32 + self.treble * 0.12, 1.0, 0.24)
        glow = np.exp(-((distance / 0.065) ** 2))
        intensity[:] = np.maximum(
            intensity,
            glow * broken * (0.13 + level * 0.16 + self.bass * 0.12),
        )
        intensity[:] = np.maximum(intensity, rim * broken * 0.82)

    def _draw_foreground_shards(
        self,
        intensity,
        highlight,
        xx,
        yy,
        horizon,
        spectrum,
        level,
    ):
        """Fill the lower right with broken low-poly edges and debris."""
        np = self._np

        # This silhouette leaves a lower-left hole. It is intentionally not
        # centred: the reference's voids feel like an off-balance cutout,
        # not a symmetrical landscape.
        #
        # The slope was 0.60-0.84 per unit of depth, which walked the edge
        # from x=-0.27 at the horizon to x=+0.27 at the bottom and left the
        # lower half of the frame reading as an empty terminal rather than
        # as deliberate negative space. Roughly a third of that now: the
        # cutout still leans, and it stops being most of the picture.
        boundary = (
            -0.42
            + (yy - horizon[None, :]) * (0.21 + self.bass * 0.13)
            + np.sin(yy * 12.0 + self.time * 0.9) * 0.045
            - self.pan * 0.14
        )
        foreground = (yy > horizon[None, :] - 0.045) & (xx > boundary)

        # Coarser triangles become torn facets. Audio bends the lattice but
        # does not make it a literal spectrum display.
        warp_x = xx + np.sin(yy * 7.0 - self.time * 1.1) * 0.075
        warp_y = yy + np.sin(xx * 5.3 + self.time * 0.66) * 0.060
        density = 3.1 + self.bass * 1.65 + self.mid * 1.20
        phase = self.time * (0.60 + self.treble * 0.88)
        edge_a = self._triangle_lines(warp_x * density + phase)
        edge_b = self._triangle_lines(
            (warp_x * 0.50 + warp_y * 0.866) * density - phase * 0.73
        )
        edge_c = self._triangle_lines(
            (warp_x * 0.50 - warp_y * 0.866) * density + phase * 0.49
        )
        edges = np.maximum(edge_a, np.maximum(edge_b, edge_c))

        # A deterministic cell hash keeps only portions of the coarse mesh,
        # breaking it into shards without a stateful random flicker.
        cell_x = np.floor((warp_x + 1.45) * 7.0)
        cell_y = np.floor((warp_y + 1.10) * 6.0)
        cell_hash = np.sin(cell_x * 127.1 + cell_y * 311.7 + 71.9)
        cell_hash = cell_hash - np.floor(cell_hash)
        kept = cell_hash > (0.39 - self.fracture * 0.18)

        depth = np.clip((yy - horizon[None, :]) / 0.86, 0.0, 1.0)
        shards = edges * foreground * kept * (0.32 + depth * 0.68)
        intensity[:] = np.maximum(
            intensity,
            shards * (0.20 + level * 0.18 + self.bass * 0.18),
        )

        # Mid/high frequencies shake free individual triangular fragments
        # just above the silhouette, giving active passages a visibly torn
        # edge while silence remains spacious.
        dust_x = np.floor((xx + 1.42) * 18.0)
        dust_y = np.floor((yy + 1.0) * 15.0)
        dust_hash = np.sin(dust_x * 91.7 + dust_y * 49.3 + self.time * 2.4)
        dust_hash = dust_hash - np.floor(dust_hash)
        dust_band = np.abs(yy - horizon[None, :]) < (0.12 + self.fracture * 0.22)
        dust = (
            (dust_hash > 0.955 - self.treble * 0.075 - self.fracture * 0.16)
            & dust_band
            & (xx > -0.50 + self.pan * 0.13)
        )
        intensity[dust] = np.maximum(
            intensity[dust],
            0.34 + self.treble * 0.23 + self.fracture * 0.24,
        )
        highlight |= dust & (self.fracture > 0.48)

    def _draw_scans(self, intensity, highlight, xx, yy, horizon, mesh_mask):
        """Sweep thin diagonal laser cuts through the upper wire field."""
        np = self._np
        if self.treble < 0.015 and self.pulse < 0.015:
            return

        # The centre travels through a broad range, so a strong diagonal is
        # an event that crosses the frame rather than a permanent stripe.
        travel = (self.time * (0.27 + self.treble * 0.44)) % 3.8 - 1.9
        diagonal = xx * 0.58 - yy * (0.92 + self.stereo * 0.14)
        beam = np.exp(-(((diagonal - travel) / 0.018) ** 2))
        echo = np.exp(-(((diagonal - travel + 0.13) / 0.030) ** 2))
        gate = np.clip(self.treble * 0.82 + self.pulse * 0.42, 0.0, 1.0)
        field = mesh_mask | (yy < horizon[None, :] + 0.10)
        strength = (beam + echo * 0.38) * field * gate
        intensity[:] = np.maximum(intensity, strength * (0.25 + self.treble * 0.39))
        # White is intentionally reserved for a hard-cut event. Normal scans
        # retain the palette's acid-green high range instead of bleaching the
        # whole lattice into a conventional laser-show visual.
        highlight |= (beam * field > 0.86) & (self.fracture > 0.45)

    def _draw_fracture_burst(self, intensity, highlight, xx, yy, horizon):
        """Throw a short cyan/white radial rupture on an actual beat onset."""
        np = self._np
        if self.fracture < 0.012:
            return

        centre_x = self.pan * 0.17
        # The origin tracks the jagged skyline so an explosion feels like it
        # is breaking through the field rather than pasted over the scene.
        centre_y = float(np.interp(centre_x, xx[0], horizon)) - 0.045
        scaled_x = (xx - centre_x) * 0.72
        scaled_y = yy - centre_y
        radius = np.sqrt(scaled_x ** 2 + scaled_y ** 2)
        angle = np.arctan2(scaled_y, scaled_x)

        rays = np.abs(np.sin(angle * 11.0 + self.time * 6.2))
        rays = rays ** (16.0 - self.fracture * 6.0)
        reach = 0.18 + self.fracture * 0.88
        envelope = np.exp(-((radius / max(reach, 0.05)) ** 2))
        front = np.exp(-(((radius - reach * 0.72) / (0.040 + self.fracture * 0.050)) ** 2))
        burst = (rays * envelope * 0.72 + front * 0.32) * self.fracture
        intensity[:] = np.maximum(intensity, burst)
        highlight |= burst > 0.46

        # A single dark cleave keeps the burst fractured rather than making
        # it a conventional smooth radial visualizer.
        cleave = np.abs(np.sin(angle * 0.5 + self.time * 1.3)) < 0.055
        cleave &= radius < reach
        intensity[cleave] *= 0.32
        highlight[cleave] = False

    def _triangle_lines(self, coordinate):
        """Return a soft one-dimensional lattice line centred at each period."""
        np = self._np
        # The distance-to-sine-zero form is cheap and antialiases naturally
        # when terminal resolution is too low to carry a true hairline.
        #
        # It does not antialias a line the raster cannot reach at all, and
        # that is what used to happen here. A fixed width of 0.075 puts the
        # falloff about 0.024 wide in coordinate units, while one braille
        # pixel advances the coordinate by roughly 0.072 at the default
        # density -- three times further than the whole line. The sampler
        # landed on a peak only by luck, so the mesh arrived as speckle
        # rather than as a lattice, and the scene looked broken beside the
        # others.
        #
        # Measure how fast the coordinate actually moves per pixel and never
        # draw narrower than that. grid.py:192 makes the same argument for
        # its ground lines: detail finer than the raster is not fine detail,
        # it is absence.
        #
        # The multiplier is the whole design. sin() is locally pi*(c - n)
        # near each zero, so a width of k * step holds the line above the
        # dither floor out to about 1.3k pixels either side. k = pi renders
        # eight-pixel lines and the three orientations close into a solid
        # wall -- the opposite failure, and just as wrong for a scene whose
        # subject is negative space. Anything past k = 0.38 already
        # guarantees a sample inside the peak, so this sits just above that:
        # certain to be hit, still thinner than one braille cell.
        gradient_y, gradient_x = np.gradient(coordinate)
        step = np.sqrt(gradient_x * gradient_x + gradient_y * gradient_y)

        width = np.maximum(0.075 + self.treble * 0.020, step * 1.15)
        return np.exp(-((np.sin(coordinate * math.pi) / width) ** 2))

    def _coordinates(self, pixel_w, pixel_h):
        key = (pixel_w, pixel_h)
        if self._grid_key == key:
            return self._grid

        np = self._np
        x = np.linspace(-1.42, 1.42, pixel_w, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, pixel_h, dtype=np.float32)
        self._grid = np.meshgrid(x, y)
        self._grid_key = key
        return self._grid

    def _sequence(self, values, fallback_size):
        """Coerce analyser output to a finite, non-negative float sequence."""
        np = self._np
        try:
            sequence = np.asarray(values, dtype=np.float32).reshape(-1)
        except (TypeError, ValueError):
            sequence = np.empty(0, dtype=np.float32)
        if sequence.size < 2:
            return np.zeros(fallback_size, dtype=np.float32)
        sequence = np.nan_to_num(sequence, nan=0.0, posinf=1.0, neginf=0.0)
        return np.clip(sequence, 0.0, 1.0)

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

    @staticmethod
    def _value(features, name, default):
        try:
            return features.get(name, default)
        except AttributeError:
            return default

    @classmethod
    def _feature(cls, features, name):
        try:
            value = features.get(name, 0.0)
        except AttributeError:
            value = 0.0
        return cls._clamp(value)

    @staticmethod
    def _signed_feature(features, name):
        try:
            value = float(features.get(name, 0.0))
        except (AttributeError, TypeError, ValueError):
            value = 0.0
        return max(-1.0, min(1.0, value))

    @staticmethod
    def _clamp(value):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

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
